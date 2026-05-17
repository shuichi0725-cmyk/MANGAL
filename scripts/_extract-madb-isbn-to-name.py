"""
MADB raw から ISBN-13 → name[0] (= 副題込みの正式 series 名) 辞書を作る。
.cache/madb-isbn-to-name.json に出力。

name[0] は schema:name の最初の要素 (= 表示用 label)。
` : 副題` 込みの full 文字列で保存 (= filter 時の strict match 用)。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".cache" / "madb" / "metadata101-clean.json"
OUT = ROOT / ".cache" / "madb-isbn-to-name.json"


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


def get_name0(name):
    if not name:
        return ""
    if isinstance(name, str):
        return name
    if isinstance(name, list) and len(name) > 0:
        first = name[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("@value", "")
    return ""


def strip_official_en(label: str) -> str:
    """name[0] の `= 英語題` 部分を剥がす。 ` : 副題` は残す。

    例:
      'ジョジョリオン = JoJolion : ジョジョの奇妙な冒険 Part8'
      → 'ジョジョリオン : ジョジョの奇妙な冒険 Part8'
      'うる星やつら : オンリー・ユー' → 'うる星やつら : オンリー・ユー'
    """
    if " = " not in label:
        return label.strip()
    parts = label.split(" = ", 1)
    title_jp = parts[0].strip()
    rest = parts[1].strip()
    if " : " in rest:
        _, sub = rest.split(" : ", 1)
        return f"{title_jp} : {sub.strip()}"
    return title_jp


def main():
    print(f"loading {RAW} ...", file=sys.stderr)
    with RAW.open("r", encoding="utf-8") as f:
        data = json.load(f)

    result = {}
    skipped = 0
    for b in data["@graph"]:
        isbn = b.get("schema:isbn", "") or ""
        if isinstance(isbn, list):
            isbn = isbn[0] if isbn else ""
        if not isinstance(isbn, str):
            isbn = str(isbn or "")
        if not isbn:
            skipped += 1
            continue
        isbn13 = normalize_isbn(isbn)
        if not isbn13:
            skipped += 1
            continue
        name0 = get_name0(b.get("schema:name"))
        if not name0:
            continue
        # `= 英語題` 部分を剥がして 主題 + 副題 のみ保持
        result[isbn13] = strip_official_en(name0)

    print(f"ISBN entries: {len(result)}, skipped (no ISBN): {skipped}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
