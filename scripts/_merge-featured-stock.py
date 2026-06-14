"""今週の一冊ストックのマージ。 .cache/featured-out/*.json (各 {items:[{slug,title,author,blurb}]})
を読み、 data/seeds/featured-stock.yml に純粋追加(既存 slug は上書きしない)。
ストックのみ=配線/公開はしない。"""
import os, glob, json, yaml

OUT_DIR = ".cache/featured-out"
SEED = "data/seeds/featured-stock.yml"

existing = {}
if os.path.exists(SEED):
    cur = yaml.safe_load(open(SEED, encoding="utf-8")) or {}
    for e in cur.get("entries", []):
        existing[e.get("slug")] = e

added = 0
for f in sorted(glob.glob(os.path.join(OUT_DIR, "*.json"))):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as ex:
        print(f"skip {f}: {ex}")
        continue
    for it in d.get("items", []):
        slug = it.get("slug")
        blurb = (it.get("blurb") or "").strip()
        if not slug or not blurb:
            continue
        if slug in existing:
            continue
        existing[slug] = {
            "slug": slug, "title": it.get("title", ""),
            "author": it.get("author", ""), "blurb": blurb,
        }
        added += 1

entries = sorted(existing.values(), key=lambda e: e.get("slug", ""))
with open(SEED, "w", encoding="utf-8") as w:
    yaml.safe_dump({"entries": entries}, w, allow_unicode=True, sort_keys=False, width=10000)
print(f"featured-stock: 新規 {added} 件追加 / 累計 {len(entries)} 件")
