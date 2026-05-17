"""
MADB raw から ISBN-13 → volume_label (= 「上」「下」「特装版」等) を抽出する。
.cache/madb-volume-labels.json に出力。

ルール:
  - volumeNumber が 純粋な数字 (= '1', '25' 等) の場合は 保存しない
    (= yml の number INTEGER で表現可能なため)
  - volumeNumber が 非数字 を含む (= '上', '下', '特装版', '上巻', '1-1' 等)
    の場合のみ 保存
  - ISBN-10 は ISBN-13 に正規化して保存
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".cache" / "madb" / "metadata101-clean.json"
OUT = ROOT / ".cache" / "madb-volume-labels.json"


def isbn10_to_isbn13(isbn10: str) -> str | None:
    digits = re.sub(r"[^0-9X]", "", isbn10.upper())
    if len(digits) != 10:
        return None
    base = "978" + digits[:9]
    total = 0
    for i, ch in enumerate(base):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    check = (10 - total % 10) % 10
    return base + str(check)


def normalize_isbn(isbn: str) -> str | None:
    s = re.sub(r"[^0-9X]", "", isbn.upper())
    if len(s) == 13:
        return s
    if len(s) == 10:
        return isbn10_to_isbn13(s)
    return None


def main():
    print(f"loading {RAW} ...", file=sys.stderr)
    with RAW.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"raw books: {len(data['@graph'])}", file=sys.stderr)

    result = {}
    saved = 0
    skipped_numeric = 0
    skipped_no_isbn = 0
    skipped_no_label = 0

    for b in data["@graph"]:
        isbn = b.get("schema:isbn", "") or ""
        vol = b.get("schema:volumeNumber", "") or ""
        # 一部の book は schema:isbn / volumeNumber が list で入ってる
        if isinstance(isbn, list):
            isbn = isbn[0] if isbn else ""
        if isinstance(vol, list):
            vol = vol[0] if vol else ""
        if not isinstance(isbn, str):
            isbn = str(isbn or "")
        if not isinstance(vol, str):
            vol = str(vol or "")
        if not vol:
            skipped_no_label += 1
            continue
        if not isbn:
            skipped_no_isbn += 1
            continue
        isbn13 = normalize_isbn(isbn)
        if not isbn13:
            skipped_no_isbn += 1
            continue
        vol = vol.strip()
        # 既定表示 `第${number}巻` で表現可能なものはスキップ:
        # - 純粋な数字 (= '1', '25')
        # - `第N巻` / `第N卷` (= 第3巻、 旧字第3卷)
        if re.match(r"^\d+$", vol):
            skipped_numeric += 1
            continue
        if re.match(r"^第\d+[巻卷]$", vol):
            skipped_numeric += 1
            continue
        result[isbn13] = vol
        saved += 1

    print(f"saved: {saved}", file=sys.stderr)
    print(f"skipped (純粋数字): {skipped_numeric}", file=sys.stderr)
    print(f"skipped (no ISBN): {skipped_no_isbn}", file=sys.stderr)
    print(f"skipped (no volumeNumber): {skipped_no_label}", file=sys.stderr)

    # サンプル
    print("\n=== sample labels ===", file=sys.stderr)
    from collections import Counter

    label_freq = Counter(result.values())
    for lbl, cnt in label_freq.most_common(20):
        print(f"  {cnt:5d} × {lbl!r}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
