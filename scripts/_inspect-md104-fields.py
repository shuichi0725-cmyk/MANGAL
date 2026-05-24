"""metadata104 = MangaBookSeries の 全 field 一覧 + 出現率 + サンプル値 を 抽出。"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

SRC = Path(".cache/madb/metadata104.json")
OUT = Path(".cache/md104-field-inventory.md")

# 各 record の 開始/終了 を 検出。 トップ level field のみ 抽出 (= ネスト value は サマリ)
RECORD_START = re.compile(r"^    \{")
RECORD_END = re.compile(r"^    \},?")
FIELD_RE = re.compile(r'^      "([^"]+)":\s*(.*)$')


def main() -> None:
    field_counts: Counter = Counter()
    field_sample: dict[str, str] = {}
    n_records = 0
    cur_fields: set[str] = set()
    in_rec = False

    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if RECORD_START.match(line):
                in_rec = True
                cur_fields = set()
                continue
            if RECORD_END.match(line):
                for k in cur_fields:
                    field_counts[k] += 1
                n_records += 1
                in_rec = False
                continue
            if not in_rec:
                continue
            m = FIELD_RE.match(line)
            if m:
                k = m.group(1)
                v = m.group(2).rstrip(",").strip()
                cur_fields.add(k)
                if k not in field_sample and v and not v.startswith("[") and not v.startswith("{"):
                    field_sample[k] = v[:80]
                elif k not in field_sample:
                    field_sample[k] = "(array or object)"

    print(f"records: {n_records:,}", file=sys.stderr)
    print(f"distinct fields: {len(field_counts)}", file=sys.stderr)

    lines = []
    lines.append("# metadata104 (= MangaBookSeries) field 一覧")
    lines.append("")
    lines.append(f"total records: **{n_records:,}**")
    lines.append("")
    lines.append("## field 出現率 (= 出現率 降順)")
    lines.append("")
    lines.append("| field | 件数 | 出現率 | サンプル |")
    lines.append("|---|---|---|---|")
    for k, c in field_counts.most_common():
        rate = c / n_records * 100
        sample = field_sample.get(k, "")
        lines.append(f"| `{k}` | {c:,} | {rate:.1f}% | {sample[:60]} |")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
