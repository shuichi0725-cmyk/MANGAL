#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アニメ季節ビューJSON生成 (= anime-season-links.jsonl + 一覧索引 → data/anime-seasons-view.json)。

サイトの /anime/[season] 頁とトップコーナーが読む表示用データ。季刊更新のたび再生成:
  harvest --season YYYY-SEASON → join → これ → 反映(コード無変更ならビルドのみ)
"""
import json, os, sys
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINKS = os.path.join(ROOT, "data", "seeds", "anime-season-links.jsonl")
INDEX = os.path.join(ROOT, "data", "manga-list-index.json")
OUT = os.path.join(ROOT, "data", "anime-seasons-view.json")

SEASON_ORDER = {"WINTER": 0, "SPRING": 1, "SUMMER": 2, "FALL": 3}

li = json.load(open(INDEX, encoding="utf-8"))
f = li["f"]
isl, it, ic, ia = f.index("slug"), f.index("title"), f.index("cover"), f.index("authors")
info = {}
for r in li["d"]:
    info[r[isl]] = {"title": r[it], "cover": r[ic],
                    "authors": [au_name(a) for a in (r[ia] or [])][:2]}

seasons = {}
n_drop = 0
seen = set()  # (season, slug) 単位でdedup(分割クールの再登場等)
for line in open(LINKS, encoding="utf-8"):
    r = json.loads(line)
    key = r["season_key"].lower().replace("fall", "autumn") if False else r["season_key"].lower()
    slug = r["slug"]
    if (key, slug) in seen:
        continue
    seen.add((key, slug))
    m = info.get(slug)
    if not m:
        n_drop += 1  # 本番索引に無い頁(除外済み等)は載せない
        continue
    seasons.setdefault(key, []).append({
        "slug": slug, "title": m["title"], "cover": m["cover"], "authors": m["authors"],
        "anime_title": r.get("anime_title"), "source": r.get("source"),
        "pop": r.get("popularity") or 0,
    })

for k in seasons:
    seasons[k].sort(key=lambda x: -x["pop"])

order = sorted(seasons.keys(), key=lambda k: (int(k.split("-")[0]), SEASON_ORDER[k.split("-")[1].upper()]))
json.dump({"order": order, "seasons": seasons},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
size = os.path.getsize(OUT) // 1024
print(f"{len(order)}季 / {sum(len(v) for v in seasons.values())}作品 / 索引不在drop {n_drop} → {os.path.relpath(OUT, ROOT)} ({size}KB)")
