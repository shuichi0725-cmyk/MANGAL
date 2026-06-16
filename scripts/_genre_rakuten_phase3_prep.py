#!/usr/bin/env python3
"""
Phase③ 準備 = 適用対象を v2 caption で batch化。
対象 union = provisional(genre適用対象) ∪ theme tag未保有(tag適用対象)。
各 work の適格性(needs_genre / needs_tag)を target-meta.json に保存(適用時に参照)。
"""
import json, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
BATCH_DIR = OUT / "target-batches"
BATCH_DIR.mkdir(parents=True, exist_ok=True)
BATCH = 40


def main():
    meta = {}
    items = []
    n_g = n_t = 0
    for line in (OUT / "corpus-v2.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        needs_genre = bool(r.get("provisional"))           # trusted空=AI暫定
        needs_tag = not bool(r.get("has_theme_tag"))       # theme tag未保有
        if not (needs_genre or needs_tag):
            continue
        slug = r["slug"]
        meta[slug] = {"needs_genre": needs_genre, "needs_tag": needs_tag}
        items.append({"id": slug, "caption": r["caption"]})
        n_g += needs_genre; n_t += needs_tag

    (OUT / "target-meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"union 対象 {len(items):,}(genre適格 {n_g:,} / tag適格 {n_t:,})", flush=True)

    for p in BATCH_DIR.glob("*.json"):
        p.unlink()
    nb = 0
    for i in range(0, len(items), BATCH):
        (BATCH_DIR / f"batch-{nb:04d}.json").write_text(
            json.dumps(items[i:i+BATCH], ensure_ascii=False, indent=1), encoding="utf-8")
        nb += 1
    print(f"batches: {nb} ({BATCH}/batch) → {BATCH_DIR}", flush=True)


if __name__ == "__main__":
    main()
