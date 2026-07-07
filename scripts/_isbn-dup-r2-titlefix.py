#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ R2 = 「題不一致のみ」層(集合一致×著者一致×題違い)を楽天題で裁定。

各クラスタの共有ISBN全冊を .cache/isbn-title-map.json(楽天題)で引き、巻数表記を剥いで正規化:
  - 上位題が80%以上に収斂 → 同一作の表記違い = dedup。canonical=楽天題に最も合致する頁
  - 割れる → union汚染(こわい本型) = 分割案件 → docs/production-diagnostics/isbn-dup-split.tsv
出力: .cache/isbn-dup-auto.json (R1と同形式 = _isbn-dup-apply.py 再利用)
※分類のみ(本番不変)。
"""
import os, re, sys, json, csv, unicodedata
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
QUEUE = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-queue.tsv")
TM = json.load(open(os.path.join(ROOT, ".cache", "isbn-title-map.json"), encoding="utf-8"))

OLDGLYPH = str.maketrans({"國":"国","學":"学","龍":"竜","藝":"芸","澤":"沢","邊":"辺","齋":"斎",
                          "眞":"真","櫻":"桜","惡":"悪","團":"団","戰":"戦","髙":"高","圓":"円",
                          "寶":"宝","豐":"豊","濱":"浜"})
PUNCT = re.compile(r"[\s　・=\-〜~×!！?？。、.,:：;；'’\"「」『』()（）\[\]〔〕【】&＆♥❤☆★…]+")
VOLPAT = re.compile(r"([（(]\s*\d+\s*[)）]|第\s*\d+\s*巻|\d+\s*巻|[Vv][Oo][Ll]\.?\s*\d+|\s+\d+\s*$)")

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
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")
RE_CATCH = re.compile(r"^catch:", re.M)
RE_ANILIST = re.compile(r"^anilist_id:\s*\d+", re.M)
RE_SUB = re.compile(r"^subtitle:\s*(.+?)\s*$", re.M)

def read_page(stem):
    p = os.path.join(SRC, stem + ".yml")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8").read()
    sub = RE_SUB.search(t)
    return {"stem": stem,
            "slug": (RE_SLUG.search(t).group(1) if RE_SLUG.search(t) else stem),
            "title": (RE_TITLE.search(t).group(1) if RE_TITLE.search(t) else stem).strip("'\""),
            "isbns": frozenset(RE_ISBN.findall(t)),
            "rich": (2 if RE_CATCH.search(t) else 0) + (1 if RE_ANILIST.search(t) else 0)
                    + (1 if (sub and sub.group(1) != "null") else 0)}

clusters = []
with open(QUEUE, encoding="utf-8") as f:
    r = csv.reader(f, delimiter="\t")
    next(r)
    for row in r:
        if row[0] == "題不一致":
            clusters.append(row[1].split(","))

auto, split, flag = [], [], []
for stems in clusters:
    pages = [p for p in (read_page(s) for s in stems) if p]
    if len(pages) < 2:
        continue
    isbns = set.union(*[set(p["isbns"]) for p in pages])
    votes = Counter()
    unknown = 0
    for i in sorted(isbns):
        t = TM.get(i)
        if not t:
            unknown += 1
            continue
        votes[norm(strip_vol(t))] += 1
    known = sum(votes.values())
    if not known:
        flag.append((stems, "楽天題キャッシュ0件", "")); continue
    top, top_n = votes.most_common(1)[0]
    coverage = top_n / known
    # ★少数派ガード: top以外の楽天題グループがどれかの頁題と一致 = その頁は実在の別作品の可能性
    #   (闇都市伝説×キミノトナリ型)。dedupすると実作品頁を消すので必ずSPLIT(per-case)へ。
    page_norms = {norm(p["title"]) for p in pages}
    minority_hits = [k for k, v in votes.items() if k != top and k in page_norms]
    if coverage < 0.9 or minority_hits:
        # 複数作品名に割れる = union汚染 = 分割案件
        split.append((stems, [p["title"] for p in pages],
                      ("少数派頁題一致:" + ",".join(m[:14] for m in minority_hits) + "; " if minority_hits else "")
                      + "; ".join(f"{k[:20]}×{v}" for k, v in votes.most_common(4))))
        continue
    # canonical = 楽天top題に最も合う頁
    def match_score(p):
        pn = norm(p["title"])
        if pn == top: return 2
        if pn and (pn in top or top in pn): return 1
        return 0
    scored = sorted(pages, key=lambda p: (match_score(p), p["rich"], len(p["isbns"])), reverse=True)
    best = scored[0]
    if match_score(best) == 0:
        flag.append((stems, f"楽天top題({top[:24]})がどの頁題とも不一致", str(votes.most_common(2)))); continue
    ties = [p for p in pages if match_score(p) == match_score(best) and p is not best]
    # 同点でも rich/巻数 で決定的に選べているので tie は許容(scored順)
    auto.append({"canonical": best["stem"], "canonical_slug": best["slug"], "title": best["title"],
                 "author_differ": False, "evidence": f"楽天題{top_n}/{known}冊が「{strip_vol(TM.get(sorted(isbns)[0],''))[:20]}」系に収斂",
                 "drops": [{"stem": p["stem"], "slug": p["slug"], "title": p["title"]}
                           for p in pages if p is not best],
                 "isbns": len(isbns)})

json.dump(auto, open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
sp = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-split.tsv")
with open(sp, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["stems", "page_titles", "rakuten_title_groups"])
    for s, t, v in split:
        w.writerow([",".join(s), " / ".join(t), v])

print(f"題不一致クラスタ: {len(clusters)}群")
print(f"  AUTO2(楽天題が単一作品に収斂=dedup可): {len(auto)}群 / drop {sum(len(a['drops']) for a in auto)}頁")
print(f"  SPLIT(union汚染=分割案件): {len(split)}群 → {os.path.relpath(sp, ROOT)}")
print(f"  FLAG(判定不能): {len(flag)}群")
for s, why, ev in flag[:10]:
    print(f"    {s} {why} {ev[:60]}")
print("\n== AUTO2 サンプル15 ==")
for a in auto[:15]:
    print(f"  keep {a['canonical']}({a['title'][:20]}) / drop {[(d['stem'], d['title'][:16]) for d in a['drops']]}")
