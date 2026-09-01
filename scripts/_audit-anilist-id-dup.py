#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同一anilist_idを複数頁が共有する組の監査 (= 薬屋/左きき型 2026-09-01型化)。

2亜種:
  A) 誤共有型(薬屋のひとりごと/左ききのエレン型) = AniListに**別エントリが実在**するのに
     同題別コミカライズ2頁が同じaidを持つ。アニメ季節join/エンリッチが誤った頁に着地する実害。
     是正= anilist-link-overrides.yml(relink)+confirmed登録(実例: 99022/113322, 109228/109229)。
  B) フランチャイズ扇形型(楳図こわい本×13頁/みこすり半劇場×9頁) = AniList側が1エントリしか
     持たない多頁シリーズ。誤りではないがenrich(synopsis等)が全頁に同内容で乗る点は留意。
判定材料としてAniList側の同題エントリ数は持たない(APIレス)。titleの異同で並べるのみ=裁定は人/AI。

出力: docs/production-diagnostics/anilist-id-dup.tsv
月次: 新規増加分(特に2頁組×同題=A型疑い)を見る。
"""
import glob, io, os, re, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "anilist-id-dup.tsv")

by_aid = {}
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    txt = open(p, encoding="utf-8", errors="replace").read(4000)
    m = re.search(r"^anilist_id:\s*(\d+)", txt, re.M)
    if not m:
        continue
    t = re.search(r"^title:\s*(.+)$", txt, re.M)
    a = re.search(r"^-?\s*name:\s*(.+)$", txt, re.M)
    by_aid.setdefault(m.group(1), []).append(
        (os.path.basename(p)[:-4], (t.group(1).strip() if t else ""), (a.group(1).strip() if a else "")))

dups = {a: v for a, v in by_aid.items() if len(v) > 1}
n_pair_same_title = 0
with open(OUT, "w", encoding="utf-8", newline="") as f:
    f.write("aid\tn_pages\tkind_hint\tslug\ttitle\tfirst_author\n")
    for a, v in sorted(dups.items(), key=lambda kv: (len(kv[1]), kv[0])):
        titles = {re.sub(r"\s", "", t) for _, t, _ in v}
        hint = "A?同題ペア" if len(v) == 2 and len(titles) == 1 else \
               ("A?同題複数" if len(titles) == 1 else "B?扇形/別題")
        if hint == "A?同題ペア":
            n_pair_same_title += 1
        for s, t, au in v:
            f.write(f"{a}\t{len(v)}\t{hint}\t{s}\t{t}\t{au}\n")
print(f"aid付き頁 {sum(len(x) for x in by_aid.values())} / 重複aid組 {len(dups)} "
      f"(うち2頁×同題=A型疑い {n_pair_same_title})")
print(f"→ {os.path.relpath(OUT, ROOT)}")
