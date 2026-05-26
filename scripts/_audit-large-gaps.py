"""gap 30+ の 大型抜け cluster を 見やすい list 形式 で 抽出。

ユーザ レビュー対象 (= 「これ 知ってる作品?」 「同シリーズか?」 の 確認用)。
出力 = .cache/large-gaps.md (= markdown 表) + .cache/large-gaps.csv。

各行:
- title (= 表示用)
- max / present / gap / sid 数 (= シリーズ統合状況)
- 取込済 巻番号 概要 (= 連続 or 飛び)
- missing 概要

加えて 分類タグ:
  [bug?]  = pres=1, max>=10 → title 数字混入 bug 疑い
  [整合?] = sid>=3 → 統合済だが MADB data 不整合 残り
  [大型]  = max>=50
  [中型]  = max 20-49
"""
from __future__ import annotations
import csv
from pathlib import Path

CSV = Path(".cache/volume-gaps.csv")
OUT_MD = Path(".cache/large-gaps.md")
OUT_CSV = Path(".cache/large-gaps.csv")

THRESHOLD = 30  # gap 30+ のみ


def classify(r) -> str:
    tags = []
    if r["present"] == 1 and r["max_vol"] >= 10:
        tags.append("bug?")
    if r["series_id_count"] >= 3:
        tags.append("整合?")
    if r["max_vol"] >= 50:
        tags.append("大型")
    elif r["max_vol"] >= 20:
        tags.append("中型")
    return " ".join(tags)


def summarize_missing(missing_str: str, max_show: int = 12) -> str:
    """missing 番号 list を 連続範囲 圧縮 形式に。"""
    if not missing_str:
        return ""
    nums = [int(x) for x in missing_str.split(",") if x.strip()]
    if not nums:
        return ""
    # 連続 range 圧縮
    ranges = []
    s = nums[0]
    p = s
    for n in nums[1:]:
        if n == p + 1:
            p = n
        else:
            ranges.append((s, p))
            s = n
            p = n
    ranges.append((s, p))
    parts = []
    for a, b in ranges:
        parts.append(str(a) if a == b else f"{a}-{b}")
    out = ", ".join(parts[:max_show])
    if len(parts) > max_show:
        out += f" ... ({len(parts) - max_show} more ranges)"
    return out


def main() -> None:
    rows = []
    with CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["max_vol"] = int(r["max_vol"])
            r["present"] = int(r["present"])
            r["gap_count"] = int(r["gap_count"])
            r["series_id_count"] = int(r["series_id_count"])
            if r["gap_count"] >= THRESHOLD:
                rows.append(r)

    rows.sort(key=lambda x: (-x["gap_count"], -x["max_vol"]))
    print(f"対象: gap >= {THRESHOLD} の cluster = {len(rows)} 件")

    # markdown 表
    md_lines = [
        f"# 大型抜け cluster (= gap >= {THRESHOLD})",
        f"",
        f"合計 {len(rows)} 件、 累計 gap {sum(r['gap_count'] for r in rows):,}",
        f"",
        f"タグ: `bug?` = title 数字混入 疑い、 `整合?` = MADB 内部不整合 疑い、 `大型`/`中型` = max 巻数",
        f"",
        f"| # | タグ | max | 取込 | 抜け | sid | title | edition | 抜け範囲 |",
        f"|--:|---|--:|--:|--:|--:|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        tags = classify(r)
        miss = summarize_missing(r["missing"])
        title = r["series_title"].replace("|", "\\|")
        md_lines.append(
            f"| {i} | {tags} | {r['max_vol']} | {r['present']} | {r['gap_count']} | "
            f"{r['series_id_count']} | {title} | {r['edition_type']} | {miss} |"
        )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    # CSV (= 操作可能形式)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "rank", "tags", "max_vol", "present", "gap_count",
                "series_id_count", "series_title", "edition_type",
                "missing_compact", "cluster_key", "missing_full",
            ],
        )
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow({
                "rank": i,
                "tags": classify(r),
                "max_vol": r["max_vol"],
                "present": r["present"],
                "gap_count": r["gap_count"],
                "series_id_count": r["series_id_count"],
                "series_title": r["series_title"],
                "edition_type": r["edition_type"],
                "missing_compact": summarize_missing(r["missing"], max_show=30),
                "cluster_key": r["cluster_key"],
                "missing_full": r["missing"],
            })

    print(f"wrote: {OUT_MD}")
    print(f"wrote: {OUT_CSV}")


if __name__ == "__main__":
    main()
