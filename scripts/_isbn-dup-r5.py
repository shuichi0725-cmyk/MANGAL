#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ R5 = 残クラスタへ R4確立手順を適用する判定器。

手順(R4知見 = memory isbn-dup-cleanup-state):
  1. クラスタ化(現 isbn-dup-pages.tsv)
  2. canonical = 基底題(自題が他メンバー題に包含される頁を優先) > 楽天多数派match > rich > 冊数
  3. 各メンバー: 隠れ本(own⊄union) → SPLIT / 家族(自本楽天題×canonical題 相互substring過半 or
     メンバー題がcanonical題を包含) かつ 同著者 → DEDUP / それ以外 → SPLIT
  4. 著者不一致メンバーは DEDUP しない(homonym防御) → SPLIT
分類のみ(本番不変)。出力: 判定ログ(全行) + .cache/isbn-dup-auto.json + .cache/isbn-dup-blocks-r5.json
適用は人が判定ログを確認してから。
"""
import os, re, sys, json, csv, sqlite3, unicodedata
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TM = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))
con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))

OLDGLYPH = str.maketrans({"國":"国","學":"学","龍":"竜","藝":"芸","澤":"沢","邊":"辺","齋":"斎",
                          "眞":"真","櫻":"桜","惡":"悪","團":"団","戰":"戦","髙":"高","圓":"円",
                          "寶":"宝","豐":"豊","濱":"浜"})
PUNCT = re.compile(r"[\s　・=\-〜~×!！?？。、.,:：;；'’\"「」『』()（）\[\]〔〕【】&＆♥❤☆★…]+")
VOLPAT = re.compile(r"([（(][^（()）]*[)）]|第\s*\d+\s*巻|\d+\s*巻|[Vv][Oo][Ll]\.?\s*\d+|\s+\d+\s*$|\d+$)")

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).translate(OLDGLYPH)
    return PUNCT.sub("", t).lower()

def strip_vol(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    prev = None
    while prev != t:
        prev = t
        t = VOLPAT.sub("", t).strip()
    return t

RE_SLUG = re.compile(r"^slug:\s*(.+?)\s*$", re.M)
RE_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
RE_AUTHOR = re.compile(r"^- name:\s*(.+?)\s*$", re.M)
RE_SKEY = re.compile(r"^_skey:\s*(.+?)\s*$", re.M)
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")
RE_CATCH = re.compile(r"^catch:", re.M)

def read_page(stem):
    mp = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
    sp = os.path.join(ROOT, "data", "manga", stem + ".yml")
    if not os.path.exists(mp):
        return None
    t = open(mp, encoding="utf-8").read()
    s = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
    skey = (RE_SKEY.search(s).group(1) if RE_SKEY.search(s) else "").strip("'\"")
    sid = None
    if skey:
        r = con.execute("SELECT id FROM series WHERE series_key=?", (skey,)).fetchone()
        sid = r[0] if r else None
    own = set()
    if sid:
        own = {r[0] for r in con.execute("""SELECT v.isbn13 FROM editions e
            JOIN volumes v ON v.edition_id=e.id WHERE e.series_id=? AND v.isbn13 IS NOT NULL""", (sid,))}
    return {"stem": stem, "sid": sid, "own": own,
            "slug": (RE_SLUG.search(t).group(1) if RE_SLUG.search(t) else stem),
            "title": (RE_TITLE.search(t).group(1) if RE_TITLE.search(t) else stem).strip("'\""),
            "author": (RE_AUTHOR.search(t).group(1) if RE_AUTHOR.search(t) else ""),
            "isbns": set(RE_ISBN.findall(t)),
            "rich": 1 if RE_CATCH.search(t) else 0}

# クラスタ化
pairs = []
with open(os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-pages.tsv"), encoding="utf-8") as f:
    r = csv.reader(f, delimiter="\t")
    next(r)
    for row in r:
        if row[0] == "DUP_PAGE":
            pairs.append((row[4], row[7]))
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
for a, b in pairs:
    parent[find(a)] = find(b)
clusters = defaultdict(set)
for a, b in pairs:
    clusters[find(a)].update([a, b])

auto, blocks, log = [], set(), []
review = []
for members in clusters.values():
    pages = [p for p in (read_page(s) for s in sorted(members)) if p and p["sid"]]
    if len(pages) < 2:
        continue
    union = set().union(*[p["isbns"] for p in pages])
    votes = Counter()
    for i in union:
        rt = TM.get(i)
        if rt:
            votes[norm(strip_vol(rt))] += 1
    top = votes.most_common(1)[0][0] if votes else ""
    def cscore(p):
        pn = norm(p["title"])
        base = sum(1 for q in pages if q is not p and pn and pn in norm(q["title"]))  # 基底題=他題に包含
        m = 2 if pn == top else (1 if pn and top and (pn in top or top in pn) else 0)
        return (base, m, p["rich"], len(p["own"]))
    pages.sort(key=cscore, reverse=True)
    canon = pages[0]
    cn = norm(canon["title"])
    tag = f"[{canon['stem']}({canon['title'][:14]})]"
    splits, dedups = [], []
    for p in pages[1:]:
        hidden = p["own"] - union
        pn = norm(p["title"])
        # 家族: メンバー題がcanonical題を包含 or 自本楽天題の過半がcanonical題と相互substring
        fam = bool(cn and cn in pn)
        if not fam:
            hits = tot = 0
            for i in p["own"]:
                rt = TM.get(i)
                if not rt:
                    continue
                rn = norm(strip_vol(rt))
                if not rn:
                    continue
                tot += 1
                if rn in cn or cn in rn:
                    hits += 1
            fam = tot > 0 and hits / tot >= 0.5
        same_author = p["author"] == canon["author"]
        if hidden:
            splits.append(p); log.append(f"SPLIT  {tag} {p['stem']}({p['title'][:14]}) 隠れ{len(hidden)}")
        elif fam and same_author:
            dedups.append(p); log.append(f"DEDUP  {tag} {p['stem']}({p['title'][:14]})")
        elif fam and not same_author:
            review.append((canon["stem"], p["stem"], "家族だが著者不一致"))
            log.append(f"REVIEW {tag} {p['stem']}({p['title'][:14]}) 家族×著者不一致({p['author'][:8]}≠{canon['author'][:8]})")
        else:
            splits.append(p); log.append(f"SPLIT  {tag} {p['stem']}({p['title'][:14]}) 非家族")
    if dedups:
        auto.append({"canonical": canon["stem"], "canonical_slug": canon["slug"], "title": canon["title"],
                     "author_differ": False,
                     "drops": [{"stem": p["stem"], "slug": p["slug"], "title": p["title"]} for p in dedups],
                     "isbns": len(union)})
    for sp in splits:
        for p in pages:
            if p is not sp:
                blocks.add((min(sp["sid"], p["sid"]), max(sp["sid"], p["sid"]),
                            f"{sp['title'][:12]} × {p['title'][:12]}"))
    # サブ断片block(splitがある群のみ)
    if splits:
        page_sids = {p["sid"] for p in pages}
        for i in union:
            for hsid, htitle in con.execute("""SELECT s.id, s.title FROM series s
                JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
                WHERE v.isbn13=?""", (i,)).fetchall():
                if hsid in page_sids:
                    continue
                hn = norm(strip_vol(htitle))
                for p in pages:
                    pn = norm(p["title"])
                    if not (hn in pn or pn in hn):
                        blocks.add((min(hsid, p["sid"]), max(hsid, p["sid"]),
                                    f"サブ断片{htitle[:10]} × {p['title'][:10]}"))

json.dump(auto, open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(sorted([list(b) for b in blocks]),
          open(os.path.join(ROOT, ".cache", "isbn-dup-blocks-r5.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"クラスタ{len(clusters)}: dedup{len(auto)}群{sum(len(a['drops']) for a in auto)}頁 / block{len(blocks)} / review{len(review)}")
print("\n".join(sorted(log)))
