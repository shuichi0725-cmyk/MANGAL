"""三世代ストックのマージ。 .cache/sansedai-out/*.json (各 {persona, gen, items:[{slug,title,comment}]})
を読み、 data/seeds/sansedai-stock.yml に純粋追加(既存 slug×persona は上書きしない)。
ストックのみ=配線/公開はしない。"""
import os, glob, json, yaml

OUT_DIR = ".cache/sansedai-out"
SEED = "data/seeds/sansedai-stock.yml"

existing = {}
if os.path.exists(SEED):
    cur = yaml.safe_load(open(SEED, encoding="utf-8")) or {}
    for e in cur.get("entries", []):
        existing[(e.get("persona"), e.get("slug"))] = e

added = 0
for f in sorted(glob.glob(os.path.join(OUT_DIR, "*.json"))):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as ex:
        print(f"skip {f}: {ex}")
        continue
    persona = d.get("persona")
    gen = d.get("gen")
    for it in d.get("items", []):
        slug = it.get("slug")
        comment = (it.get("comment") or "").strip()
        if not slug or not comment:
            continue
        key = (persona, slug)
        if key in existing:
            continue
        existing[key] = {
            "persona": persona, "gen": gen, "slug": slug,
            "title": it.get("title", ""), "comment": comment,
        }
        added += 1

entries = list(existing.values())
entries.sort(key=lambda e: (e.get("gen", ""), e.get("persona", ""), e.get("slug", "")))
with open(SEED, "w", encoding="utf-8") as w:
    yaml.safe_dump({"entries": entries}, w, allow_unicode=True, sort_keys=False, width=10000)
print(f"sansedai-stock: 新規 {added} 件追加 / 累計 {len(entries)} 件")
