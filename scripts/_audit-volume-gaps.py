"""種2 sqlite を 走査して、 連続する 巻番号 に 抜けが出るシリーズ を 一覧化。

判定:
- volumes.number を edition 単位で集計 (= standard / bunkobon は別 edition)
- 整数化できる number のみ対象 (= 「上」「下」「番外」 等は除外)
- is_extra=1 は除外
- 1 〜 max(N) のうち 欠番を抽出
- max <= 2 (= 1〜2 巻完結) は noise なので除外

出力: top N (= 抜け数多い順 / max 多い順) + 全件 csv。
"""
from __future__ import annotations
import csv
import re
import sqlite3
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")
OUT_CSV = Path(".cache/volume-gaps.csv")
OUT_TOP = Path(".cache/volume-gaps-top.txt")
TOP_N = 80
MIN_MAX = 3   # max 巻 が これ未満の series は noise として skip
MAX_MAX = 300 # max 巻 が これ超 = 発行年混入 等の data noise として skip

NUM_RE = re.compile(r"^\s*(\d+)\s*$")


def to_int(s: str | None) -> int | None:
    if s is None:
        return None
    m = NUM_RE.match(str(s))
    return int(m.group(1)) if m else None


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"missing: {DB}")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        """
        SELECT
          s.id              AS series_id,
          s.title           AS series_title,
          s.title_official_en AS title_en,
          e.id              AS edition_id,
          e.type            AS edition_type,
          e.label           AS edition_label,
          v.number          AS vol_number,
          v.is_extra        AS is_extra
        FROM volumes v
        JOIN editions e ON e.id = v.edition_id
        JOIN series s   ON s.id = e.series_id
        ORDER BY s.id, e.id, v.number
        """
    ).fetchall()

    # edition 単位で 集計
    buckets: dict[tuple[int, int], dict] = {}
    for r in rows:
        if r["is_extra"]:
            continue
        n = to_int(r["vol_number"])
        if n is None or n <= 0:
            continue
        key = (r["series_id"], r["edition_id"])
        b = buckets.setdefault(
            key,
            {
                "series_id": r["series_id"],
                "series_title": r["series_title"],
                "title_en": r["title_en"] or "",
                "edition_id": r["edition_id"],
                "edition_type": r["edition_type"] or "",
                "edition_label": r["edition_label"] or "",
                "numbers": set(),
            },
        )
        b["numbers"].add(n)

    results = []
    for b in buckets.values():
        nums = b["numbers"]
        mx = max(nums)
        if mx < MIN_MAX or mx > MAX_MAX:
            continue
        expected = set(range(1, mx + 1))
        missing = sorted(expected - nums)
        if not missing:
            continue
        results.append(
            {
                "series_id": b["series_id"],
                "series_title": b["series_title"],
                "title_en": b["title_en"],
                "edition_id": b["edition_id"],
                "edition_type": b["edition_type"],
                "edition_label": b["edition_label"],
                "max_vol": mx,
                "present": len(nums),
                "gap_count": len(missing),
                "missing": ",".join(str(x) for x in missing),
            }
        )

    # 抜け数 多い順 → max 多い順
    results.sort(key=lambda x: (-x["gap_count"], -x["max_vol"]))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "series_id",
                "series_title",
                "title_en",
                "edition_id",
                "edition_type",
                "edition_label",
                "max_vol",
                "present",
                "gap_count",
                "missing",
            ],
        )
        w.writeheader()
        w.writerows(results)

    # console (= PowerShell の Shift-JIS) では化けるので file 出力 メインに
    lines = []
    lines.append("=== 巻番号 gap 精査 結果 ===")
    lines.append(f"対象 edition (= max>={MIN_MAX} かつ max<={MAX_MAX}): {len(buckets):,}")
    lines.append(f"gap あり: {len(results):,}")
    lines.append(f"csv: {OUT_CSV}")
    lines.append("")
    lines.append(f"--- top {TOP_N} (= gap 数多い順) ---")
    lines.append(f"{'gap':>4} {'max':>4} {'pres':>4}  {'edition':<10}  title  (missing)")
    lines.append("-" * 110)
    for r in results[:TOP_N]:
        title = r["series_title"]
        if r["edition_label"] and r["edition_label"] != title:
            title = f"{title} [{r['edition_label']}]"
        miss = r["missing"]
        if len(miss) > 60:
            miss = miss[:60] + "..."
        lines.append(
            f"{r['gap_count']:>4} {r['max_vol']:>4} {r['present']:>4}  "
            f"{r['edition_type']:<10}  {title}  ({miss})"
        )
    OUT_TOP.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # ASCII summary は console にも出す
    print(f"target editions: {len(buckets):,}  gap-containing: {len(results):,}")
    print(f"csv: {OUT_CSV}")
    print(f"top: {OUT_TOP}")


if __name__ == "__main__":
    main()
