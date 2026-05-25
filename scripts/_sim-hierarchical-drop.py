"""階層的派生本排除 dry-run sim。

階層:
  1. 強 drop = 既存 DROP_TITLE_CONTAINS_PATTERNS hit → 無条件 drop (= override 無効)
  2. 派生判定 = 同 qid 内 主軸 (= title prefix 親) の 巻数比率 < 5% sid = drop 候補
  3. keep override = 派生候補のうち title に「カラー/フルカラー/大全集/復刻版」 含む = keep に翻す

drop 対象 list 出力 + 副作用確認。
"""
from __future__ import annotations
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]; sys.argv = ["_", "--no-filter"]
spec.loader.exec_module(audit); sys.argv = saved

DB = Path(".cache/db-v2.sqlite")
OUT = Path(".cache/sim-hierarchical-drops.csv")

THRESHOLD_PCT = 1.0  # 主軸巻数 1% 未満 = 派生候補 (= 確実派生のみ drop、 巻き添え避け)

KEEP_OVERRIDE_PATTERNS = [
    "フルカラー", "総カラー", "オールカラー", "カラー版", "カラーエディション",
    "大全集", "復刻版", "復刊",
]


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # qid 紐付き sid + vol_count
    rows = con.execute("""
        SELECT s.id, s.qid, s.title,
               COUNT(DISTINCT v.id) AS vc
        FROM series s
        LEFT JOIN editions e ON e.series_id=s.id
        LEFT JOIN volumes v ON v.edition_id=e.id AND v.is_extra=0
        WHERE s.qid IS NOT NULL
        GROUP BY s.id
    """).fetchall()

    by_qid = defaultdict(list)
    for r in rows:
        by_qid[r["qid"]].append((r["id"], r["title"] or "", r["vc"]))

    drop_strong = []     # 階層 1
    drop_derivative = [] # 階層 2 (= override で救済されなかった)
    keep_override = []   # 階層 3 (= 救済)
    keep_main = []       # 主軸自体 (= 階層対象外)
    keep_independent = []# 同 qid 1 sid (= 階層対象外)

    for qid, sids in by_qid.items():
        if len(sids) < 2:
            for sid, t, vc in sids:
                if not audit.title_passes(t):
                    drop_strong.append((sid, qid, t, vc, "single+strong"))
                else:
                    keep_independent.append((sid, qid, t, vc))
            continue
        # 同 qid 内 main = 巻数最多 sid
        main_sid, main_title, main_vc = max(sids, key=lambda x: x[2])
        for sid, t, vc in sids:
            # 階層 1 = 強 drop
            if not audit.title_passes(t):
                drop_strong.append((sid, qid, t, vc, "strong"))
                continue
            if sid == main_sid:
                keep_main.append((sid, qid, t, vc, main_vc))
                continue
            # title が main_title の prefix で 始まる? (= 同シリーズ派生)
            # title 完全一致 (= sub 違い) は 派生候補対象
            if not t.startswith(main_title):
                # 別作品扱い (= 同 qid 別 title) → keep
                keep_independent.append((sid, qid, t, vc))
                continue
            # 階層 2 = 派生候補 (= 主軸 5% 未満)
            ratio = vc / main_vc * 100 if main_vc else 0
            if ratio >= THRESHOLD_PCT:
                # 別シリーズ (= ストーンオーシャン 27% 等)、 keep
                keep_independent.append((sid, qid, t, vc))
                continue
            # 派生候補
            if any(p in t for p in KEEP_OVERRIDE_PATTERNS):
                # 階層 3 = override で keep
                keep_override.append((sid, qid, t, vc, main_title, main_vc, ratio))
            else:
                drop_derivative.append((sid, qid, t, vc, main_title, main_vc, ratio))

    print(f"=== 階層的排除 sim (= 巻数閾値 {THRESHOLD_PCT}%) ===\n")
    print(f"対象 qid: {len(by_qid):,}")
    print(f"keep main (= 主軸)             : {len(keep_main):,}")
    print(f"keep independent (= 別作品扱い) : {len(keep_independent):,}")
    print(f"keep override (= カラー等で救済): {len(keep_override):,}")
    print(f"drop strong (= 階層 1 強 drop) : {len(drop_strong):,}")
    print(f"drop derivative (= 階層 2 派生): {len(drop_derivative):,}")
    print()
    print(f"--- keep override 例 (= 派生だが カラー/大全集 等で keep) ---")
    for sid, qid, t, vc, mt, mvc, ratio in keep_override[:20]:
        print(f"  sid={sid:>6} vc={vc:>3} ratio={ratio:.1f}% '{t}' (main: '{mt}' vc={mvc})")
    print()
    print(f"--- drop derivative 例 (= 派生本 = drop) top 30 ---")
    drop_derivative.sort(key=lambda x: -x[5])
    for sid, qid, t, vc, mt, mvc, ratio in drop_derivative[:30]:
        print(f"  sid={sid:>6} vc={vc:>3} ratio={ratio:.1f}% '{t}' (main: '{mt}' vc={mvc})")

    # csv
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "sid", "qid", "title", "vol_count", "main_title", "main_vc", "ratio_pct"])
        for sid, qid, t, vc, *_ in drop_strong:
            w.writerow(["drop_strong", sid, qid, t, vc, "", "", ""])
        for sid, qid, t, vc, mt, mvc, r in drop_derivative:
            w.writerow(["drop_derivative", sid, qid, t, vc, mt, mvc, f"{r:.1f}"])
        for sid, qid, t, vc, mt, mvc, r in keep_override:
            w.writerow(["keep_override", sid, qid, t, vc, mt, mvc, f"{r:.1f}"])
    print(f"\n  csv: {OUT}")


if __name__ == "__main__":
    main()
