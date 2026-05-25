"""現在の volume-gaps.csv を 種類別に 分類して 件数集計。

分類軸:
  A. pres=1 & max>=10 = title 数字 number 混入 bug の 強い疑い
  B. pres<gap で 同 cluster 内 series_id 多数 = MADB data 不整合 (= 救済可能性)
  C. 単純 大型シリーズ continuation (= 「ちび本当にあった笑える話」 等)
  D. その他 (= 真の MADB 抜け / 表記揺れ残り 等)

gap 規模:
  large (= 30+)、 medium (= 10-29)、 small (= 1-9)
"""
from __future__ import annotations
import csv
from pathlib import Path

CSV = Path(".cache/volume-gaps.csv")


def main() -> None:
    rows = []
    with CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["max_vol"] = int(r["max_vol"])
            r["present"] = int(r["present"])
            r["gap_count"] = int(r["gap_count"])
            r["series_id_count"] = int(r["series_id_count"])
            rows.append(r)

    total = len(rows)
    total_gap = sum(r["gap_count"] for r in rows)
    print(f"=== 現状 audit gap 整理 ===")
    print(f"  対象 cluster (= gap あり): {total:,}")
    print(f"  累計 gap 件数 (= 全 cluster 合算): {total_gap:,}")
    print()

    # 分類 A = pres==1 & max>=10 (= title 数字混入 bug 疑い = 1 巻完結なのに max が大きい)
    class_a = [r for r in rows if r["present"] == 1 and r["max_vol"] >= 10]
    class_a_gap = sum(r["gap_count"] for r in class_a)
    print(f"  A. pres=1 & max>=10 (= title 数字混入 bug 疑い):")
    print(f"     cluster {len(class_a):,}、 累計 gap {class_a_gap:,}")

    # 分類 B = sid>=3 (= cluster 統合済だが まだ 不整合残る)
    class_b = [r for r in rows if r not in class_a and r["series_id_count"] >= 3]
    class_b_gap = sum(r["gap_count"] for r in class_b)
    print(f"  B. sid>=3 (= 複数 series_id 統合済 = MADB data 不整合 残り 疑い):")
    print(f"     cluster {len(class_b):,}、 累計 gap {class_b_gap:,}")

    # 分類 C = 大型シリーズ (= max>=50)
    class_c = [r for r in rows
               if r not in class_a and r not in class_b
               and r["max_vol"] >= 50]
    class_c_gap = sum(r["gap_count"] for r in class_c)
    print(f"  C. max>=50 (= 月刊風 大型シリーズ continuation):")
    print(f"     cluster {len(class_c):,}、 累計 gap {class_c_gap:,}")

    # 分類 D = 残り
    class_d = [r for r in rows
               if r not in class_a and r not in class_b and r not in class_c]
    class_d_gap = sum(r["gap_count"] for r in class_d)
    print(f"  D. その他 (= 真の MADB 抜け / 表記揺れ残り 等):")
    print(f"     cluster {len(class_d):,}、 累計 gap {class_d_gap:,}")

    print()
    print(f"=== gap 規模別 ===")
    for label, lo, hi in [("large (= 30+)", 30, 10**6),
                          ("medium (= 10-29)", 10, 29),
                          ("small (= 1-9)", 1, 9)]:
        c = [r for r in rows if lo <= r["gap_count"] <= hi]
        cg = sum(r["gap_count"] for r in c)
        print(f"  {label}: cluster {len(c):,}、 累計 gap {cg:,}")

    print()
    print(f"=== max 規模別 ===")
    for label, lo, hi in [("100+", 100, 10**6),
                          ("50-99", 50, 99),
                          ("20-49", 20, 49),
                          ("10-19", 10, 19),
                          ("3-9", 3, 9)]:
        c = [r for r in rows if lo <= r["max_vol"] <= hi]
        cg = sum(r["gap_count"] for r in c)
        print(f"  max {label}: cluster {len(c):,}、 累計 gap {cg:,}")

    print()
    print(f"=== 推移 (= これまでの段階) ===")
    print(f"  v1 (旧 edition 単位)         : 75,188 edition / 19,863 gap")
    print(f"  v2 (cluster 統合)            : 34,356 cluster / 5,375 gap")
    print(f"  v2.5 (norm 強化 option A)    : 34,289 / 5,339")
    print(f"  v3 (series-merge 7 cluster)  : 34,286 / {total:,}")


if __name__ == "__main__":
    main()
