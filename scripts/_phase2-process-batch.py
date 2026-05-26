"""Phase 2 batch processor。

入力 = raw batch JSON (= {key: segmented_kana_or_null})
処理:
  - segmented あり → fill_dict[key] = {title_kana: スペース除去版, title_kana_segmented: segmented}
  - segmented null → unknown list に key 追加 (= AI 自信なし)
出力:
  - data/seeds/_fills/phase2-batch-NNN.json = apply 形式 (= _apply-fills.ts で 適用可能)
  - data/seeds/_fills/phase2-unknown.json 蓄積更新
  - data/seeds/_fills/phase2-todo.json から 該当 key 除外

使用 = python _phase2-process-batch.py --batch 1 --raw .cache/phase2-raw-1.json
"""
from __future__ import annotations
import json
import re
import sys
import argparse
from pathlib import Path

TODO = Path("data/seeds/_fills/phase2-todo.json")
UNKNOWN = Path("data/seeds/_fills/phase2-unknown.json")
FILLS_DIR = Path("data/seeds/_fills")

HAS_SPACE = re.compile(r"[\s　]+")


def to_kana_pair(segmented: str) -> tuple[str, str]:
    """segmented (= スペースあり) → (title_kana, title_kana_segmented) 同 logic Phase 1。"""
    seg = segmented.strip()
    no_space = HAS_SPACE.sub("", seg)
    return (no_space, seg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--raw", type=Path, required=True)
    args = ap.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    todo = json.loads(TODO.read_text(encoding="utf-8"))
    unknown = json.loads(UNKNOWN.read_text(encoding="utf-8"))

    todo_by_key = {e["key"]: e for e in todo}
    fill_dict = {}
    new_unknown = []
    n_unknown_already_in_list = 0
    unknown_keys = set(u["key"] for u in unknown)

    for key, segmented in raw.items():
        if key not in todo_by_key:
            print(f"  [warn] key not in todo: {key}", file=sys.stderr)
            continue
        if segmented is None or segmented == "":
            # unknown / skip
            if key in unknown_keys:
                n_unknown_already_in_list += 1
            else:
                entry = todo_by_key[key]
                new_unknown.append({
                    "key": key,
                    "title": entry["title"],
                    "subtitle": entry.get("subtitle"),
                    "qid": entry.get("qid"),
                    "alt_en": entry.get("alt_en"),
                    "synopsis": entry.get("synopsis"),
                })
        else:
            title_kana, segmented_clean = to_kana_pair(segmented)
            fill_dict[key] = {
                "title_kana": title_kana,
                "title_kana_segmented": segmented_clean,
            }

    # output batch fill JSON
    batch_path = FILLS_DIR / f"phase2-batch-{args.batch:03d}.json"
    batch_path.write_text(json.dumps(fill_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {batch_path} ({len(fill_dict)} fills)")

    # update unknown
    unknown.extend(new_unknown)
    UNKNOWN.write_text(json.dumps(unknown, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  unknown +{len(new_unknown)} (total {len(unknown)})")

    # update todo (= 除外)
    processed_keys = set(raw.keys())
    todo_remaining = [e for e in todo if e["key"] not in processed_keys]
    TODO.write_text(json.dumps(todo_remaining, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  todo: {len(todo)} → {len(todo_remaining)} (-{len(todo) - len(todo_remaining)})")

    # summary
    print(f"  batch {args.batch}: fills={len(fill_dict)} unknown={len(new_unknown)} processed={len(raw)}")


if __name__ == "__main__":
    main()
