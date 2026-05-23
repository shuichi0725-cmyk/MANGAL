"""metadata101.json から ノイズ contentRating の record の rdfs:label を抜く.

ノイズ判定 = '成年' / '成人' を含まない かつ 空でない 値。
record 単位 buffer = 6-space indent の `    {` 〜 `    },?`。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")

LABEL_RE = re.compile(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"')
RATING_RE = re.compile(r'^      "schema:contentRating":\s*"((?:[^"\\]|\\.)*)"')
ID_RE = re.compile(r'^      "@id":\s*"([^"]+)"')


def is_noise(rating: str) -> bool:
    return rating != "" and "成年" not in rating and "成人" not in rating


def main() -> int:
    noise: list[dict] = []
    buf_label: str | None = None
    buf_id: str | None = None
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("    {"):
                buf_label = None
                buf_id = None
                continue
            m = LABEL_RE.match(line)
            if m:
                buf_label = json.loads(f'"{m.group(1)}"')
                continue
            m = ID_RE.match(line)
            if m:
                buf_id = m.group(1).rsplit("/", 1)[-1]
                continue
            m = RATING_RE.match(line)
            if m:
                rating = json.loads(f'"{m.group(1)}"')
                if is_noise(rating):
                    noise.append({"id": buf_id, "label": buf_label, "rating": rating})

    by_rating: dict[str, list[dict]] = {}
    for r in noise:
        by_rating.setdefault(r["rating"], []).append(r)

    print(f"# ノイズ contentRating 一覧 (= {len(noise)} 件)")
    print()
    for rating in sorted(by_rating, key=lambda k: -len(by_rating[k])):
        rows = by_rating[rating]
        print(f"## rating = `{rating}` ({len(rows)} 件)")
        print()
        for row in rows:
            print(f"- {row['id']} : {row['label']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
