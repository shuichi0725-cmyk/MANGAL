"""
data/manga/*.yml の各 volume が、 yml の series identity (= title [+ : subtitle])
と raw MADB の name[0] で 厳格一致するか確認し、 不一致 volume を除外する。

dry-run mode (= default): 除外候補のみ表示、 ファイル不変更。
apply mode (= --apply): 実際に yml から該当 volume を削除。

filter logic:
  expected = yml.title + (' : ' + yml.subtitle if yml.subtitle else '')
  for each volume v:
    name0 = isbn_to_name[v.isbn13]
    if name0 == expected: keep
    elif normalize(name0) == normalize(expected): keep   # 全/半角等の揺れ吸収
    else: REMOVE
  ISBN が cache に無い volume は 保守的に keep (= 除外しない)

注: edition 単位ではなく volume 単位で filter。 edition が空になったら
    edition ごと削除。
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISBN_NAME = ROOT / ".cache" / "madb-isbn-to-name.json"
MANGA_DIR = ROOT / "data" / "manga"


def normalize_name(s: str) -> str:
    """全/半角・スペース・記号差を吸収する正規化。"""
    if not s:
        return ""
    s = s.replace("　", " ")
    s = re.sub(r"\s+", "", s)
    # NFKC 簡易 (全角→半角): Python str.translate でやれない複雑なものは諦め
    s = s.replace("：", ":").replace("：", ":")
    return s.lower()


def parse_yml_meta(text: str) -> dict:
    """yml から title / subtitle / editions list を抜き出す。 YAML parser 不使用
    (= 行ベース、 既存スタイル保持のため)。"""
    m_title = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
    m_sub = re.search(r"^subtitle:\s*(.+)$", text, re.MULTILINE)
    title = m_title.group(1).strip().strip('"') if m_title else ""
    subtitle = m_sub.group(1).strip().strip('"') if m_sub else ""
    return {"title": title, "subtitle": subtitle}


def split_volume_blocks(text: str) -> list[tuple[int, int, str]]:
    """各 volume block の (start_line, end_line, block_text) を返す。"""
    lines = text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s+)- number:\s*(\d+)\s*$", lines[i])
        if not m:
            i += 1
            continue
        indent = m.group(1)
        item_indent = indent + "  "
        start = i
        end = i + 1
        while end < len(lines):
            nl = lines[end]
            if re.match(rf"^{re.escape(indent)}- number:", nl):
                break
            if nl and not nl.startswith(item_indent):
                break
            end += 1
        blocks.append((start, end, "\n".join(lines[start:end])))
        i = end
    return blocks


def extract_isbn(block: str) -> str | None:
    m = re.search(r'isbn13:\s*"?(\d{13})"?', block)
    return m.group(1) if m else None


def split_edition_blocks(text: str) -> list[tuple[int, int]]:
    """editions: list 配下の各 edition の行範囲。"""
    lines = text.split("\n")
    res = []
    # editions: keyword 開始行を見つける
    ed_start = None
    for i, l in enumerate(lines):
        if re.match(r"^editions:\s*$", l):
            ed_start = i + 1
            break
    if ed_start is None:
        return res
    # 各 edition block (= 行頭 "  - type:" で始まり 次の "  - type:" or 末尾まで)
    i = ed_start
    while i < len(lines):
        if re.match(r"^  - type:", lines[i]):
            start = i
            end = i + 1
            while end < len(lines):
                if re.match(r"^  - type:", lines[end]):
                    break
                if lines[end] and not lines[end].startswith("    "):
                    break
                end += 1
            res.append((start, end))
            i = end
        else:
            i += 1
    return res


EDITION_KEYWORDS = (
    "完全版",
    "新装版",
    "文庫版",
    "文庫",
    "愛蔵版",
    "ワイド版",
    "新装再編版",
    "リニューアル",
    "カバーリニューアル",
    "限定版",
    "新装",
    "新版",
    "復刻版",
    "豪華版",
)


def check_volume(isbn: str | None, expected_title: str, isbn_name: dict) -> tuple[bool, str]:
    """(matches, name_in_madb) を返す。 ISBN cache に無ければ matches=True (= 保守的)。

    判定 rule (= 緩め):
      - 完全一致 (= name[0] == expected_title) → OK
      - 末尾 '.' を剥がして一致 (= NDL convention) → OK
      - name[0] が 'expected_title : <edition_keyword>' → OK (= 別 edition も同一作品)
      - それ以外 → mismatch
    """
    if not isbn:
        return (True, "(no ISBN)")
    name = isbn_name.get(isbn)
    if name is None:
        return (True, "(ISBN not in cache)")
    exp_norm = normalize_name(expected_title)
    name_norm = normalize_name(name)
    name_norm_no_dot = re.sub(r"\.+$", "", name_norm)
    if name_norm == exp_norm or name_norm_no_dot == exp_norm:
        return (True, name)
    # `expected : <edition_keyword>` 形式
    if name.startswith(expected_title + " : "):
        rest = name[len(expected_title) + 3 :].strip()
        # rest が edition keyword (= 完全版 等) なら OK
        if rest in EDITION_KEYWORDS:
            return (True, name)
        # 副題込み yml の場合 (= うる星やつら2 : ビューティフル・ドリーマー) は
        # 上位の expected_title 自体が `title : subtitle` で組まれて来るので、 ここに
        # は来ない。
    return (False, name)


def process_yml(path: Path, isbn_name: dict, apply: bool) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = parse_yml_meta(text)
    title = meta["title"]
    subtitle = meta["subtitle"]
    expected = f"{title} : {subtitle}" if subtitle else title

    blocks = split_volume_blocks(text)
    stats = {
        "yml": path.name,
        "title": title,
        "expected": expected,
        "total": len(blocks),
        "matched": 0,
        "skipped_no_isbn": 0,
        "mismatches": [],
    }
    mismatch_blocks = []
    for start, end, block in blocks:
        isbn = extract_isbn(block)
        ok, name_madb = check_volume(isbn, expected, isbn_name)
        if ok:
            if isbn and isbn in isbn_name:
                stats["matched"] += 1
            else:
                stats["skipped_no_isbn"] += 1
            continue
        stats["mismatches"].append(
            {
                "isbn": isbn,
                "name_madb": name_madb,
                "block_lines": (start, end),
            }
        )
        mismatch_blocks.append((start, end))

    # 全 volume mismatch なら yml ごと空になるので apply skip + 警告
    if apply and mismatch_blocks:
        n_keep = stats["total"] - len(stats["mismatches"])
        if n_keep == 0:
            stats["skipped_would_empty"] = True
            return stats
        # remove blocks
        lines = text.split("\n")
        delete_mask = [False] * len(lines)
        for s, e in mismatch_blocks:
            for idx in range(s, e):
                delete_mask[idx] = True
        new_lines = [l for i, l in enumerate(lines) if not delete_mask[i]]
        new_text = "\n".join(new_lines)
        new_text = remove_empty_editions(new_text)
        path.write_text(new_text, encoding="utf-8")
    return stats


def remove_empty_editions(text: str) -> str:
    """volumes: の直後に - number: 行が無い edition を削除。"""
    lines = text.split("\n")
    res = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^  - type:", line):
            # 同 edition block の範囲を測る
            start = i
            end = i + 1
            while end < len(lines):
                if re.match(r"^  - type:", lines[end]):
                    break
                if lines[end] and not lines[end].startswith("    "):
                    break
                end += 1
            block = lines[start:end]
            block_text = "\n".join(block)
            # volumes: 配下に - number: 行が無いか確認
            has_vol = re.search(r"^      - number:", block_text, re.MULTILINE)
            if has_vol:
                res.extend(block)
            # else: skip (= edition ごと削除)
            i = end
        else:
            res.append(line)
            i += 1
    return "\n".join(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実適用 (= デフォルトは dry-run)")
    ap.add_argument("--verbose", action="store_true", help="mismatch 詳細表示")
    args = ap.parse_args()

    print(f"loading {ISBN_NAME} ...", file=sys.stderr)
    with ISBN_NAME.open("r", encoding="utf-8") as f:
        isbn_name = json.load(f)
    print(f"ISBN entries: {len(isbn_name)}", file=sys.stderr)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n=== {mode} ===\n")

    total_yml = 0
    total_vol = 0
    total_match = 0
    total_no_isbn = 0
    total_mismatch = 0
    yml_with_mismatch = 0

    for path in sorted(MANGA_DIR.glob("*.yml")):
        s = process_yml(path, isbn_name, args.apply)
        total_yml += 1
        total_vol += s["total"]
        total_match += s["matched"]
        total_no_isbn += s["skipped_no_isbn"]
        n_mm = len(s["mismatches"])
        total_mismatch += n_mm
        if n_mm == 0:
            continue
        yml_with_mismatch += 1
        print(f"━━━ {s['yml']} ({n_mm} 件 mismatch / 全 {s['total']} 巻)")
        print(f"   expected: {s['expected']!r}")
        for mm in s["mismatches"]:
            print(f"     ISBN {mm['isbn']}  →  {mm['name_madb']!r}")

    print()
    print("=" * 60)
    print(f"yml total            : {total_yml}")
    print(f"yml with mismatch    : {yml_with_mismatch}")
    print(f"volume total         : {total_vol}")
    print(f"  matched            : {total_match}")
    print(f"  no ISBN cache hit  : {total_no_isbn} (= 保守的に keep)")
    print(f"  mismatched (REMOVE): {total_mismatch}")


if __name__ == "__main__":
    main()
