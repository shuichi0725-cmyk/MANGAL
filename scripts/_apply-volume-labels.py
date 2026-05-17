"""
.cache/madb-volume-labels.json を data/manga/*.yml に適用する。

各 volume の isbn13 で lookup し、 該当 label があれば volume_label を追加。

YAML 操作は string regex ベース (= 既存スタイル保持のため YAML loader 不使用)。
volume block の最後の field の直後に `        volume_label: <value>` を挿入。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / ".cache" / "madb-volume-labels.json"
MANGA_DIR = ROOT / "data" / "manga"

stats = {
    "yml_scanned": 0,
    "yml_changed": 0,
    "volumes_total": 0,
    "volumes_labeled": 0,
    "volumes_skipped_existing": 0,
}


def quote_yaml(s: str) -> str:
    """YAML scalar の最小エスケープ。 安全なら 引用符なし、 そうでなければ double quote。"""
    if re.match(r"^[ぁ-んァ-ヿ一-鿿A-Za-z0-9\- 　・]+$", s):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def process_yml(path: Path, labels: dict) -> bool:
    stats["yml_scanned"] += 1
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # volume の境界を見つける: `      - number: N` の行で 1 volume 始まる
    new_lines: list[str] = []
    i = 0
    changed = False
    while i < len(lines):
        m = re.match(r"^(\s+)- number:\s*(\d+)\s*$", lines[i])
        if not m:
            new_lines.append(lines[i])
            i += 1
            continue
        # この volume block の終わりまで走査
        indent = m.group(1)
        item_indent = indent + "  "
        block_start = i
        block_end = i + 1
        while block_end < len(lines):
            nl = lines[block_end]
            # 次の volume の `      - number:` か、 outdent 行で終わる
            if re.match(rf"^{re.escape(indent)}- number:", nl):
                break
            if nl and not nl.startswith(item_indent):
                break
            block_end += 1
        stats["volumes_total"] += 1

        # block 内に既に volume_label がある ?
        block = lines[block_start:block_end]
        if any(re.match(rf"^{re.escape(item_indent)}volume_label:", l) for l in block):
            stats["volumes_skipped_existing"] += 1
            new_lines.extend(block)
            i = block_end
            continue

        # block 内の isbn13 を抽出
        isbn13 = None
        for l in block:
            mm = re.match(rf'^{re.escape(item_indent)}isbn13:\s*"?(\d{{13}})"?', l)
            if mm:
                isbn13 = mm.group(1)
                break
        if isbn13 and isbn13 in labels:
            label = labels[isbn13]
            # number 行の直後に volume_label を挿入
            new_block = list(block)
            for idx, l in enumerate(new_block):
                if re.match(rf"^{re.escape(indent)}- number:", l):
                    new_block.insert(
                        idx + 1, f"{item_indent}volume_label: {quote_yaml(label)}"
                    )
                    break
            new_lines.extend(new_block)
            stats["volumes_labeled"] += 1
            changed = True
        else:
            new_lines.extend(block)
        i = block_end

    if changed:
        path.write_text("\n".join(new_lines), encoding="utf-8")
        stats["yml_changed"] += 1
    return changed


def main():
    print(f"loading {LABELS} ...", file=sys.stderr)
    with LABELS.open("r", encoding="utf-8") as f:
        labels = json.load(f)
    print(f"labels: {len(labels)}", file=sys.stderr)

    for p in sorted(MANGA_DIR.glob("*.yml")):
        process_yml(p, labels)

    print("\n=== result ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
