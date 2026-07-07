#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ R3 = 同題×同著者×ISBN集合が包含関係(⊆) の層を dedup (こち亀型)。

小さい方の集合が大きい方に完全包含 = 小頁は固有情報を持たない重複 → superset頁をcanonical。
部分重なり(相互に固有ISBNあり)は per-case のまま残す。
出力: .cache/isbn-dup-auto.json (= _isbn-dup-apply.py 再利用)。分類のみ・本番不変。
"""
import os, re, sys, json, csv, unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
QUEUE = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-queue.tsv")

OLDGLYPH = str.maketrans({"國":"国","學":"学","龍":"竜","藝":"芸","澤":"沢","邊":"辺","齋":"斎",
                          "眞":"真","櫻":"桜","惡":"悪","團":"団","戰":"戦","髙":"高","圓":"円",
                          "寶":"宝","豐":"豊","濱":"浜"})
PUNCT = re.compile(r"[\s　・=\-〜~×!！?？。、.,:：;；'’\"「」『』()（）\[\]〔〕【】&＆♥❤☆★…]+")
def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).translate(OLDGLYPH)
    return PUNCT.sub("", t).lower()

RE_SLUG = re.compile(r"^slug:\s*(.+?)\s*$", re.M)
RE_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
RE_AUTHOR = re.compile(r"^- name:\s*(.+?)\s*$", re.M)
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")
RE_CATCH = re.compile(r"^catch:", re.M)
RE_ANILIST = re.compile(r"^anilist_id:\s*\d+", re.M)

def read_page(stem):
    p = os.path.join(SRC, stem + ".yml")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8").read()
    return {"stem": stem,
            "slug": (RE_SLUG.search(t).group(1) if RE_SLUG.search(t) else stem),
            "title": (RE_TITLE.search(t).group(1) if RE_TITLE.search(t) else stem).strip("'\""),
            "author": (RE_AUTHOR.search(t).group(1) if RE_AUTHOR.search(t) else ""),
            "isbns": frozenset(RE_ISBN.findall(t)),
            "rich": (2 if RE_CATCH.search(t) else 0) + (1 if RE_ANILIST.search(t) else 0)}

clusters = []
with open(QUEUE, encoding="utf-8") as f:
    r = csv.reader(f, delimiter="\t")
    next(r)
    for row in r:
        if row[0] == "集合不一致":  # 題一致×著者一致×集合違い のみ
            clusters.append(row[1].split(","))

auto, rest = [], []
for stems in clusters:
    pages = [p for p in (read_page(s) for s in stems) if p]
    if len(pages) < 2:
        continue
    if len({norm(p["title"]) for p in pages}) != 1 or len({p["author"] for p in pages}) != 1:
        rest.append((stems, "再読で題/著者不一致")); continue
    pages.sort(key=lambda p: (len(p["isbns"]), p["rich"]), reverse=True)
    sup = pages[0]
    if all(p["isbns"] <= sup["isbns"] for p in pages[1:]):
        auto.append({"canonical": sup["stem"], "canonical_slug": sup["slug"], "title": sup["title"],
                     "author_differ": False,
                     "drops": [{"stem": p["stem"], "slug": p["slug"], "title": p["title"]}
                               for p in pages[1:]],
                     "isbns": len(sup["isbns"])})
    else:
        uniq = {p["stem"]: len(p["isbns"] - sup["isbns"]) for p in pages[1:]}
        rest.append((stems, f"相互固有あり{uniq}"))

json.dump(auto, open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"集合不一致(題著者一致)クラスタ: {len(clusters)}群")
print(f"  AUTO3(包含=subset重複): {len(auto)}群 / drop {sum(len(a['drops']) for a in auto)}頁")
for a in auto:
    print(f"    keep {a['canonical']}({a['isbns']}冊) / drop {[d['stem'] for d in a['drops']]}")
print(f"  残(部分重なり=per-case): {len(rest)}群")
for s, why in rest:
    print(f"    {s} {why}")
