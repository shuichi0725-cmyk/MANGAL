#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISBNダブリ潰し triage (= _audit-isbn-dup-pages.py の結果を処理層別。 2026-07-07)。

クラスタ(連結成分)単位で分類:
  AUTO  : 全頁 同著者 × 正規化同題 × ISBN集合完全一致 = 純粋二重出力 → page-dedup 一括安全
          (同一ISBN集合=物理的に同じ本の集合なので、外部確証なしで dedup 可。
           canonical = メタ充実度[subtitle/catch/anilist/巻数] → slug品質 で決定的選択)
  QUEUE : 題が違う(分割案件=こわい本型/巻割れ型) or 部分重なり(混入案件) → per-case
出力: .cache/isbn-dup-auto.json / docs/production-diagnostics/isbn-dup-queue.tsv
※このスクリプトは分類のみ(本番不変)。 適用は _isbn-dup-apply.py。
"""
import os, re, sys, json, csv, unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
TSV = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-pages.tsv")

# 旧字体等の同一視(題正規化用)
OLDGLYPH = str.maketrans({"國":"国","學":"学","龍":"竜","藝":"芸","澤":"沢","邊":"辺","齋":"斎",
                          "眞":"真","櫻":"桜","惡":"悪","團":"団","戰":"戦","髙":"高","圓":"円",
                          "寶":"宝","豐":"豊","濱":"浜"})
PUNCT = re.compile(r"[\s　・=\-〜~×!！?？。、.,:：;；'’\"「」『』()（）\[\]〔〕【】&＆♥❤☆★…]+")

def norm_title(t):
    t = unicodedata.normalize("NFKC", str(t or "")).translate(OLDGLYPH)
    return PUNCT.sub("", t).lower()

RE_SLUG = re.compile(r"^slug:\s*(.+?)\s*$", re.M)
RE_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
RE_SUB = re.compile(r"^subtitle:\s*(.+?)\s*$", re.M)
RE_AUTHOR = re.compile(r"^- name:\s*(.+?)\s*$", re.M)
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")
RE_CATCH = re.compile(r"^catch:", re.M)
RE_ANILIST = re.compile(r"^anilist_id:\s*\d+", re.M)

def read_page(stem):
    p = os.path.join(SRC, stem + ".yml")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8").read()
    m = RE_TITLE.search(t)
    title = (m.group(1) if m else stem).strip("'\"")
    sub = RE_SUB.search(t)
    return {
        "stem": stem,
        "slug": (RE_SLUG.search(t).group(1) if RE_SLUG.search(t) else stem),
        "title": title,
        "subtitle": (sub.group(1).strip("'\"") if sub and sub.group(1) != "null" else ""),
        "author": (RE_AUTHOR.search(t).group(1) if RE_AUTHOR.search(t) else ""),
        "isbns": frozenset(RE_ISBN.findall(t)),
        "rich": (2 if RE_CATCH.search(t) else 0) + (1 if RE_ANILIST.search(t) else 0)
                + (1 if (sub and sub.group(1) != "null") else 0),
        "vols": len(RE_ISBN.findall(t)),
    }

# ペア読込 → 連結成分
pairs = []
with open(TSV, encoding="utf-8") as f:
    r = csv.reader(f, delimiter="\t")
    next(r)
    for row in r:
        pairs.append((row[4], row[7]))

parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    parent[find(a)] = find(b)
for a, b in pairs:
    union(a, b)
clusters = defaultdict(set)
for a, b in pairs:
    clusters[find(a)].update([a, b])

BROKEN = re.compile(r"[〔〕\^-]")  # 化け題signal(PUA/怪しい括弧)

auto, queue = [], []
for members in clusters.values():
    pages = [read_page(s) for s in sorted(members)]
    pages = [p for p in pages if p]
    if len(pages) < 2:
        continue
    titles = {norm_title(p["title"]) for p in pages}
    authors = {p["author"] for p in pages}
    sets = {p["isbns"] for p in pages}
    # AUTO条件: 正規化同題 × ISBN集合完全一致(同一の物理本集合=外部確証不要)。
    # 著者表記違いは許容(空手バカ一代型=同作の作画交代でMADB著者クラスタが割れた断片。集合一致が同一性の証明)
    if len(titles) == 1 and len(sets) == 1 and pages[0]["isbns"]:
        # canonical選択: 題が化けてない > メタ充実 > 巻数 > slug短い(年suffix無し優先)
        def key(p):
            return (0 if BROKEN.search(p["title"]) else 1, p["rich"], p["vols"],
                    0 if re.search(r"-\d{4}$", p["stem"]) else 1, -len(p["stem"]))
        pages.sort(key=key, reverse=True)
        auto.append({"canonical": pages[0]["stem"], "canonical_slug": pages[0]["slug"],
                     "title": pages[0]["title"],
                     "author_differ": len(authors) > 1,
                     "drops": [{"stem": p["stem"], "slug": p["slug"], "title": p["title"]}
                               for p in pages[1:]],
                     "isbns": len(pages[0]["isbns"])})
    else:
        why = []
        if len(titles) > 1: why.append("題不一致")
        if len(authors) > 1: why.append("著者不一致")
        if len(sets) > 1: why.append("集合不一致")
        queue.append({"stems": [p["stem"] for p in pages],
                      "titles": [p["title"] for p in pages],
                      "authors": sorted({p["author"] for p in pages}),
                      "why": "+".join(why)})

json.dump(auto, open(os.path.join(ROOT, ".cache", "isbn-dup-auto.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
qout = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-queue.tsv")
with open(qout, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["why", "stems", "titles", "authors"])
    for q in queue:
        w.writerow([q["why"], ",".join(q["stems"]), " / ".join(q["titles"]), " / ".join(q["authors"])])

print(f"クラスタ: {len(clusters)}群")
print(f"AUTO(純粋二重出力=機械dedup可): {len(auto)}群 / drop対象 {sum(len(a['drops']) for a in auto)}頁")
print(f"QUEUE(per-case): {len(queue)}群 → {os.path.relpath(qout, ROOT)}")
print("\n== AUTO サンプル10 ==")
for a in auto[:10]:
    print(f"  {a['title'][:24]} : keep {a['canonical']} / drop {[d['stem'] for d in a['drops']]}")
print("\n== QUEUE 内訳 ==")
whys = defaultdict(int)
for q in queue:
    whys[q["why"]] += 1
for k, v in sorted(whys.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}群")
