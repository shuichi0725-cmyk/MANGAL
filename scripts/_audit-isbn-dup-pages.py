#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本番ページ間 ISBN ダブリ監査 (= D・N・A²分裂型の検出器。 2026-07-07 ユーザ要望)。

data/manga.v2 全頁を走査し、 同一 isbn13 が複数ページに載っているものを検出。
ページペア単位で重なり率により分類:
  - DUP_PAGE  : 共有ISBN数 ≥ 小さい方の頁の50% = 頁丸ごと重複(DNA型分裂)候補 → page-dedup 対象
  - SHARED_FEW: 少数ISBNだけ共有 = 混入/帯またぎ(過merge・別作混入)候補 → per-case調査
※調査のみ・本番不変。 出力: docs/production-diagnostics/isbn-dup-pages.tsv
使い方: python scripts/_audit-isbn-dup-pages.py
"""
import os, re, sys, csv
from collections import defaultdict
from itertools import combinations

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-pages.tsv")

RE_SLUG = re.compile(r"^slug:\s*(.+?)\s*$", re.M)
RE_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
RE_AUTHOR = re.compile(r"^- name:\s*(.+?)\s*$", re.M)
RE_ISBN = re.compile(r"isbn13:\s*'?(\d{13})'?")

pages = {}  # stem -> (slug, title, author, set(isbn))
isbn_map = defaultdict(set)  # isbn -> set(stem)

files = [e for e in os.scandir(SRC) if e.name.endswith(".yml")]
print(f"走査: {len(files)}頁 ...", flush=True)
for e in files:
    try:
        t = open(e.path, encoding="utf-8").read()
    except Exception:
        continue
    stem = e.name[:-4]
    slug = (RE_SLUG.search(t) or [None, stem])[1] if RE_SLUG.search(t) else stem
    title = m.group(1) if (m := RE_TITLE.search(t)) else stem
    author = m.group(1) if (m := RE_AUTHOR.search(t)) else ""
    isbns = set(RE_ISBN.findall(t))
    pages[stem] = (slug, title.strip("'\""), author, isbns)
    for i in isbns:
        isbn_map[i].add(stem)

dup_isbns = {i: s for i, s in isbn_map.items() if len(s) > 1}
# ページペアに集約
pair_shared = defaultdict(set)  # (stemA, stemB) -> shared isbns
for i, stems in dup_isbns.items():
    for a, b in combinations(sorted(stems), 2):
        pair_shared[(a, b)].add(i)

rows = []
for (a, b), shared in sorted(pair_shared.items(), key=lambda kv: -len(kv[1])):
    sa, ta, aa, ia = pages[a]
    sb, tb, ab, ib = pages[b]
    small = min(len(ia), len(ib)) or 1
    ratio = len(shared) / small
    klass = "DUP_PAGE" if ratio >= 0.5 else "SHARED_FEW"
    same_author = "同著者" if aa and aa == ab else "別著者"
    rows.append([klass, f"{len(shared)}/{small}", f"{ratio:.0%}", same_author,
                 a, ta, aa, b, tb, ab, ",".join(sorted(shared)[:5]) + ("..." if len(shared) > 5 else "")])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["class", "shared/small", "ratio", "author_match",
                "stemA", "titleA", "authorA", "stemB", "titleB", "authorB", "isbns_sample"])
    w.writerows(rows)

n_dup = sum(1 for r in rows if r[0] == "DUP_PAGE")
n_few = len(rows) - n_dup
print(f"ダブリISBN: {len(dup_isbns)}個 / ページペア: {len(rows)}件")
print(f"  DUP_PAGE(頁丸ごと重複=DNA型): {n_dup}件")
print(f"  SHARED_FEW(少数混入型): {n_few}件")
print(f"→ {os.path.relpath(OUT, ROOT)}")
print("\n== DUP_PAGE 上位20 ==")
for r in rows[:60]:
    if r[0] == "DUP_PAGE":
        print(f"  {r[1]:>7} {r[3]} | {r[4]}({r[5][:18]}) × {r[7]}({r[8][:18]}) {r[6][:10]}")
