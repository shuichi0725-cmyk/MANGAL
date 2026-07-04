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
         "column-ai-league", "sansedai-archive", "art-books"]
urls = [f"{SITE}/{p}" if p else SITE for p in fixed] + [f"{SITE}/manga/{s}" for s in slugs]

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
