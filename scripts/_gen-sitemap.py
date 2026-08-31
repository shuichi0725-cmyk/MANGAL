#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sitemap生成 (= SEO②。週次蒸留のbuild後・r2-sync前に実行し out/ へ書く)

66k URL > 1ファイル上限(5万) → sitemapインデックス + 分割(4万URL/file)。
URL源 = data/manga-list-index.json(本番索引=掲載中の全slug) + 主要固定頁。
"""
import json, os, sys, math
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://mangal-db.com"
OUT = os.path.join(ROOT, "out")
CHUNK = 40000

idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
f = idx["f"]; si = f.index("slug")
slugs = [r[si] for r in idx["d"]]
fixed = ["", "list", "browse", "about", "terms", "privacy", "contact",
         "column-ai-league", "sansedai-archive", "art-books",
         "tokushu", "rankings", "anime",  # ★2026-08-04 見直しで追加(日替わり特集ほか)
         "authors", "titles"]  # ★2026-08-31 SEO(索引ハブ2本=クロール導線)
# ★動的ランディング面(2026-08-04 見直しで追加: canonical持ちの索引対象なのにsitemap漏れだった)
import yaml
dyn = []
gy = yaml.safe_load(open(os.path.join(ROOT, "data", "genres.yml"), encoding="utf-8")) or {}
dyn += [f"genre/{k}" for k in gy]  # ジャンル32面
try:
    zv = json.load(open(os.path.join(ROOT, "data", "zenshuu-view.json"), encoding="utf-8"))
    dyn += [f"zenshuu/{c['key']}" for c in zv.get("collections", []) if c.get("key")]
except OSError:
    pass
ab_dir = os.path.join(ROOT, "data", "art-books")
if os.path.isdir(ab_dir):
    for fn in sorted(os.listdir(ab_dir)):
        if fn.endswith(".yml"):
            d = yaml.safe_load(open(os.path.join(ab_dir, fn), encoding="utf-8")) or {}
            if d.get("slug"):
                dyn.append(f"art-books/{d['slug']}")
try:
    ai = yaml.safe_load(open(os.path.join(ROOT, "data", "seeds", "ai-reviews.yml"), encoding="utf-8")) or []
    secs = ai.get("sections", ai) if isinstance(ai, dict) else ai
    dyn += [f"column-ai-league/{s['setsu']}" for s in secs if isinstance(s, dict) and s.get("setsu")]
except OSError:
    pass
# ★著者頁(≈40k 2026-08-31 SEO): build成果物 out/author/*.html の実在一覧が正
#   (lib/authors.ts のキー計算をPythonで再実装しない=ドリフトでsitemapが404を撒く型の根絶。
#    sitemap生成は build後・sync前の工程なので out/ は必ず在る)。
auth_dir = os.path.join(OUT, "author")
n_auth = 0
if os.path.isdir(auth_dir):
    for fn in sorted(os.listdir(auth_dir)):
        if fn.endswith(".html") and fn != "_empty.html":
            dyn.append(f"author/{fn[:-5]}")
            n_auth += 1
if n_auth == 0:
    print("★WARN: out/author が空 → 著者頁をsitemapに載せられない(build後に実行しているか?)")
# ★題名索引ハブ(2026-08-31 SEO): 頁割りは titles-pages.json が単一ソース(app/titles と共有)
try:
    tp = json.load(open(os.path.join(ROOT, "data", "titles-pages.json"), encoding="utf-8"))
    dyn += [f"titles/{k}" for k in tp.get("parts", {})]
except OSError:
    print("★WARN: data/titles-pages.json 無し → 題名索引をsitemapに載せられない")

urls = [f"{SITE}/{p}" if p else SITE for p in fixed] + [f"{SITE}/{p}" for p in dyn] + \
    [f"{SITE}/manga/{s}" for s in slugs]

os.makedirs(OUT, exist_ok=True)
n_files = math.ceil(len(urls) / CHUNK)
for i in range(n_files):
    part = urls[i * CHUNK:(i + 1) * CHUNK]
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in part:
        body.append(f"<url><loc>{u}</loc></url>")
    body.append("</urlset>")
    open(os.path.join(OUT, f"sitemap-{i+1}.xml"), "w", encoding="utf-8").write("\n".join(body))
index = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for i in range(n_files):
    index.append(f"<sitemap><loc>{SITE}/sitemap-{i+1}.xml</loc></sitemap>")
index.append("</sitemapindex>")
open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(index))
print(f"sitemap: {len(urls):,} URL → sitemap.xml + {n_files}分割 → out/")
