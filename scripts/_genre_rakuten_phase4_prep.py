#!/usr/bin/env python3
"""
Phase④ 準備 = 2パス救済の検証タスク生成(ジャンルのみ)。
gray候補のうち RESCUE_SET ジャンルを conf≥medium で持つ provisional work を、
本文+候補ジャンル で別エージェントに再判定させる(過付与を落とし truth-gap を救う)。
"""
import json, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-rakuten"
BATCH_DIR = OUT / "phase4-batches"
BATCH_DIR.mkdir(parents=True, exist_ok=True)
BATCH = 40

# 救済対象 = 較正で不採用だが本文に根拠あれば正しいことが多いジャンル(truth-gap/閾値ぎりぎり)。
# war/historical/suspense/school/yokai/mind-game は過付与/検出不能なので除外。
RESCUE = {"isekai", "gourmet", "drama", "adventure", "ecchi", "mystery", "music", "bl"}


def main():
    cap = {}
    for line in (OUT / "corpus-v2.jsonl").open(encoding="utf-8"):
        r = json.loads(line); cap[r["slug"]] = r["caption"]

    items = []
    for line in (OUT / "gray-candidates.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if not r.get("needs_genre"):
            continue
        cands = sorted({x["key"] for x in r["genres_gray"] if x["key"] in RESCUE and x["conf"] >= 2})
        if not cands or r["slug"] not in cap:
            continue
        items.append({"id": r["slug"], "caption": cap[r["slug"]], "candidates": cands})

    print(f"Phase④ 検証対象 {len(items):,} work", flush=True)
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
