"""metadata101 を scan して シリーズ ID → 真の巻数 を 集計 (= volumeNumber dedupe)。

Output: .cache/series-bookcount.tsv  (= series_id<TAB>n_volumes_unique<TAB>n_book_records)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")
OUT = Path(".cache/series-bookcount.tsv")

ID_RE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(C\d+)"')
VOLNUM_RE = re.compile(r'"schema:volumeNumber":\s*"((?:[^"\\]|\\.)*)"')
POS_RE = re.compile(r'"schema:position":\s*"((?:[^"\\]|\\.)*)"')
ISBN_RE = re.compile(r'"schema:isbn":\s*"((?:[^"\\]|\\.)*)"')
MID_RE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(M\d+)"')


def main() -> None:
    # series_id → {volume_keys (set)}, also count book records total
    vols: dict[str, set[str]] = {}
    records: dict[str, int] = {}
    n_books = 0
    n_with_series = 0

    in_rec = False
    cur_series = ""
    cur_volnum = ""
    cur_pos = ""
    cur_isbn = ""
    cur_mid = ""
    in_ispartof = False
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("    {"):
                in_rec = True
                cur_series = ""
                cur_volnum = ""
                cur_pos = ""
                cur_isbn = ""
                cur_mid = ""
                in_ispartof = False
                continue
            if not in_rec:
                continue
            if line.rstrip().startswith("    }"):
                n_books += 1
                if cur_series:
                    # dedupe key 優先順: position (= 数値 揺れに強い) → ISBN → volumeNumber → mid
                    vkey = ""
                    if cur_pos:
                        try:
                            vkey = f"pos:{float(cur_pos)}"
                        except ValueError:
                            pass
                    if not vkey and cur_isbn:
                        vkey = f"isbn:{cur_isbn}"
                    if not vkey and cur_volnum:
                        vkey = f"vn:{cur_volnum}"
                    if not vkey:
                        vkey = f"mid:{cur_mid}"
                    vols.setdefault(cur_series, set()).add(vkey)
                    records[cur_series] = records.get(cur_series, 0) + 1
                    n_with_series += 1
                if n_books % 50000 == 0:
                    print(f"  scanned: {n_books:,}", file=sys.stderr)
                in_rec = False
                continue
            if not cur_mid:
                m = MID_RE.search(line)
                if m:
                    cur_mid = m.group(1)
            v = VOLNUM_RE.search(line)
            if v and not cur_volnum:
                cur_volnum = v.group(1)
            p = POS_RE.search(line)
            if p and not cur_pos:
                cur_pos = p.group(1)
            i = ISBN_RE.search(line)
            if i and not cur_isbn:
                cur_isbn = i.group(1)
            if '"schema:isPartOf"' in line:
                in_ispartof = True
                continue
            if in_ispartof:
                m = ID_RE.search(line)
                if m and not cur_series:
                    cur_series = m.group(1)
                if "}" in line or "]" in line:
                    in_ispartof = False

    print(f"books scanned: {n_books:,}", file=sys.stderr)
    print(f"books with isPartOf: {n_with_series:,}", file=sys.stderr)
    print(f"unique series: {len(vols):,}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        f.write("series_id\tn_volumes\tn_records\n")
        for sid in sorted(vols.keys()):
            f.write(f"{sid}\t{len(vols[sid])}\t{records[sid]}\n")
    print(f"wrote: {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
