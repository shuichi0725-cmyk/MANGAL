#!/usr/bin/env python3
"""
Phase② 準備 = held-out 3,000(同一slug)を v2 caption で batch化(信頼度較正用)。
corpus-v2.jsonl の改良caption を使う。truth はジャンル(heldout-truth)/タグ(heldout-tag-truth)既存を流用。
"""
import json, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
BATCH_DIR = OUT / "heldout-v2-batches"
BATCH_DIR.mkdir(parents=True, exist_ok=True)
BATCH = 40


def main():
    capv2 = {}
    for line in (OUT / "corpus-v2.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        capv2[r["slug"]] = r["caption"]

    held = [json.loads(l)["slug"] for l in (OUT / "heldout-truth.jsonl").open(encoding="utf-8")]
    items = [{"id": s, "caption": capv2[s]} for s in held if s in capv2]
    miss = [s for s in held if s not in capv2]
    print(f"held-out {len(held)} / v2caption有 {len(items)} / 欠損 {len(miss)}", flush=True)

    for p in BATCH_DIR.glob("*.json"):
        p.unlink()
    nb = 0
    for i in range(0, len(items), BATCH):
        (BATCH_DIR / f"batch-{nb:03d}.json").write_text(
            json.dumps(items[i:i+BATCH], ensure_ascii=False, indent=1), encoding="utf-8")
        nb += 1
    print(f"batches: {nb} → {BATCH_DIR}", flush=True)


if __name__ == "__main__":
    main()
