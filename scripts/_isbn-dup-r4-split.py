#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ R4 = SPLIT38群の最終裁定 (隠れ本/題系譜ルール)。

各クラスタ:
  1. canonical = 楽天題多数派に最も合致する頁 (R2方式)
  2. 各メンバー頁(非canonical)を判定:
     - 隠れ本あり (own ISBNs ⊄ union = number-dedupで不可視化されている) → SPLIT
     - 自本の楽天題(巻数strip)が canonical頁題と相互substringでない(過半) → SPLIT (別作品系譜)
     - それ以外 → DEDUP (canonicalへ page-dedup)
  3. SPLIT = merge-exceptions block (メンバー頁sid × 他全頁sid)。
     さらにクラスタ内の非頁home sid(サブ断片)も、題が合わない頁sidに対して block。
出力: .cache/isbn-dup-auto.json(dedup分) / .cache/isbn-dup-blocks.json(block分+対象stem)
※分類のみ・本番不変。適用は _isbn-dup-apply.py + merge-exceptions追記。
"""
import os, re, sys, json, csv, sqlite3, unicodedata
from collections import Counter

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
    return {"stem": stem,
            "slug": (RE_SLUG.search(t).group(1) if RE_SLUG.search(t) else stem),
            "title": (RE_TITLE.search(t).group(1) if RE_TITLE.search(t) else stem).strip("'\""),
            "sid": sid, "own": own,
            "isbns": set(RE_ISBN.findall(t)),
            "rich": 1 if RE_CATCH.search(t) else 0}

def family_of(own_isbns, canon_title_norm, self_title_norm):
    """自本の楽天題(strip_vol)の過半が canonical題と相互substringか"""
    hits = tot = 0
    for i in own_isbns:
        rt = TM.get(i)
        if not rt:
            continue
        rn = norm(strip_vol(rt))
        if not rn:
            continue
        tot += 1
        if rn in canon_title_norm or canon_title_norm in rn:
            hits += 1
    if tot == 0:  # 楽天無 → 頁題同士で判定
        return self_title_norm in canon_title_norm or canon_title_norm in self_title_norm
    return hits / tot >= 0.5

clusters = []
with open(os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-split.tsv"), encoding="utf-8") as f:
    r = csv.reader(f, delimiter="\t")
    next(r)
    for row in r:
        clusters.append(row[0].split(","))

auto, blocks, affected, log = [], set(), set(), []
for stems in clusters:
    pages = [p for p in (read_page(s) for s in stems) if p and p["sid"]]
    if len(pages) < 2:
        continue
    union = set().union(*[p["isbns"] for p in pages])
    # canonical選定 = 楽天題多数派match (R2方式)
    votes = Counter()
    for i in union:
        rt = TM.get(i)
        if rt:
            votes[norm(strip_vol(rt))] += 1
    top = votes.most_common(1)[0][0] if votes else ""
    def cscore(p):
        pn = norm(p["title"])
        m = 2 if pn == top else (1 if pn and top and (pn in top or top in pn) else 0)
        return (m, p["rich"], len(p["own"]))
    pages.sort(key=cscore, reverse=True)
    canon = pages[0]
    cn = norm(canon["title"])
    splits, dedups = [], []
    for p in pages[1:]:
        hidden = p["own"] - union
        fam = family_of(p["own"], cn, norm(p["title"]))
        if hidden or not fam:
            splits.append(p)
            log.append(f"SPLIT {p['stem']}({p['title'][:16]}) ← 隠れ{len(hidden)}冊 家族{'○' if fam else '✗'} / canon={canon['stem']}")
        else:
            dedups.append(p)
            log.append(f"DEDUP {p['stem']}({p['title'][:16]}) → {canon['stem']}")
    if dedups:
        auto.append({"canonical": canon["stem"], "canonical_slug": canon["slug"], "title": canon["title"],
                     "author_differ": False,
                     "drops": [{"stem": p["stem"], "slug": p["slug"], "title": p["title"]} for p in dedups],
                     "isbns": len(union)})
    # blocks: split頁sid × 他全頁sid (対称)
    for sp in splits:
        for p in pages:
            if p is not sp:
                blocks.add((min(sp["sid"], p["sid"]), max(sp["sid"], p["sid"])))
    # 非頁home sid(サブ断片): 題が合わない頁sidに対しblock
    if splits:
        page_sids = {p["sid"] for p in pages}
        for i in union:
            for (hsid, htitle) in con.execute("""SELECT s.id, s.title FROM series s
                JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
                WHERE v.isbn13=?""", (i,)).fetchall():
                if hsid in page_sids:
                    continue
                hn = norm(strip_vol(htitle))
                for p in pages:
                    pn = norm(p["title"])
                    if not (hn in pn or pn in hn):
                        blocks.add((min(hsid, p["sid"]), max(hsid, p["sid"])))
    affected.update(p["stem"] for p in pages)

json.dump(auto, open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump({"blocks": sorted(map(list, blocks)), "affected": sorted(affected)},
          open(os.path.join(ROOT, ".cache", "isbn-dup-blocks.json"), "w", encoding="utf-8"))
print(f"クラスタ{len(clusters)} → dedupクラスタ{len(auto)}(drop {sum(len(a['drops']) for a in auto)}頁) / block {len(blocks)}ペア / 影響stem {len(affected)}")
print("\n".join(log))
