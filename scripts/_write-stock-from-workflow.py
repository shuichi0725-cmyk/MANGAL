"""ワークフロー結果(result.sansedai / result.featured)を data/seeds の2シードに書き出す。
- slug実在検証(data/manga.v2/{slug}.yml が無いものは弾く=ページ不整合防止)
- HTMLエンティティ復元(&amp; 等)
- dedup(三世代=persona×slug / 今週=slug)
- 純粋追加(既存シードがあれば残す)"""
import os, sys, json, html, yaml

OUT_TASK = sys.argv[1]
MANGA = "data/manga.v2"
SAN_SEED = "data/seeds/sansedai-stock.yml"
FEAT_SEED = "data/seeds/featured-stock.yml"

raw = open(OUT_TASK, encoding="utf-8").read()
res = json.loads(raw).get("result", {})
san = res.get("sansedai", [])
feat = res.get("featured", [])

def exists(slug):
    return slug and os.path.exists(os.path.join(MANGA, slug + ".yml"))

def clean(s):
    return html.unescape((s or "").strip())

# --- 三世代 ---
san_existing = {}
if os.path.exists(SAN_SEED):
    for e in (yaml.safe_load(open(SAN_SEED, encoding="utf-8")) or {}).get("entries", []):
        san_existing[(e.get("persona"), e.get("slug"))] = e
san_added = san_dropped = 0
for it in san:
    slug = it.get("slug"); persona = it.get("persona")
    if not exists(slug):
        san_dropped += 1; continue
    key = (persona, slug)
    if key in san_existing:
        continue
    san_existing[key] = {"persona": persona, "gen": it.get("gen"), "slug": slug,
                         "title": clean(it.get("title")), "comment": clean(it.get("comment"))}
    san_added += 1
san_entries = sorted(san_existing.values(), key=lambda e: (e.get("gen", 0), e.get("persona", ""), e.get("slug", "")))
with open(SAN_SEED, "w", encoding="utf-8") as w:
    yaml.safe_dump({"entries": san_entries}, w, allow_unicode=True, sort_keys=False, width=10000)

# --- 今週 ---
feat_existing = {}
if os.path.exists(FEAT_SEED):
    for e in (yaml.safe_load(open(FEAT_SEED, encoding="utf-8")) or {}).get("entries", []):
        feat_existing[e.get("slug")] = e
feat_added = feat_dropped = 0
for it in feat:
    slug = it.get("slug")
    if not exists(slug):
        feat_dropped += 1; continue
    if slug in feat_existing:
        continue
    feat_existing[slug] = {"slug": slug, "title": clean(it.get("title")),
                           "author": clean(it.get("author")), "blurb": clean(it.get("blurb"))}
    feat_added += 1
feat_entries = sorted(feat_existing.values(), key=lambda e: e.get("slug", ""))
with open(FEAT_SEED, "w", encoding="utf-8") as w:
    yaml.safe_dump({"entries": feat_entries}, w, allow_unicode=True, sort_keys=False, width=10000)

print(f"三世代: 追加{san_added} / 不在slug除外{san_dropped} / 累計{len(san_entries)}")
print(f"今週  : 追加{feat_added} / 不在slug除外{feat_dropped} / 累計{len(feat_entries)}")
# 人格別内訳
from collections import Counter
c = Counter(e["persona"] for e in san_entries)
for p, n in sorted(c.items()):
    print(f"  {p}: {n}")
