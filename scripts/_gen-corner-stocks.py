#!/usr/bin/env python3
"""コーナー用ストックを public/data/*.json へ書き出す(クライアント日替わり選択用)。
- sansedai-stock.yml(741件) → sansedai-stock.json (gen別・cover/存在チェック付き)
- featured-stock.yml(55件)  → featured-stock.json (今日の一冊=毎日書評)
本番索引からcover補完し、本番に存在しないslugはdrop(リンク切れ防止)。再生成=このスクリプト。"""
import json, os, sys, yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
f = idx["f"]; si = f.index("slug"); ci = f.index("cover")
cover = {}
for r in idx["d"]:
    cover[r[si]] = r[ci]

os.makedirs(os.path.join(ROOT, "public", "data"), exist_ok=True)

def conv(src, out, fields):
    doc = yaml.safe_load(open(os.path.join(ROOT, "data", "seeds", src), encoding="utf-8"))
    rows = []
    dropped = 0
    for e in doc.get("entries", []):
        slug = e.get("slug")
        if slug not in cover:
            dropped += 1
            continue
        row = {k: e.get(k) for k in fields if e.get(k) is not None}
        row["cover"] = cover.get(slug)
        rows.append(row)
    json.dump(rows, open(os.path.join(ROOT, "public", "data", out), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{out}: {len(rows)}件 (本番不在drop {dropped})")
    return rows

conv("sansedai-stock.yml", "sansedai-stock.json", ["persona", "gen", "slug", "title", "comment"])
conv("featured-stock.yml", "featured-stock.json", ["slug", "title", "author", "blurb"])
