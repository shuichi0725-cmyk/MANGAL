# -*- coding: utf-8 -*-
"""週次蒸留 手順1 = 事前再生成のオーケストレータ (2026-08-26 新設)。

★背景: 生成器13本がskillの散文リストで、新機能のたび人手追記=追記漏れがそのまま
恒久stale化する構造だった(shinkan/anilist-status-map等、日付入り★追記が並ぶのが症状)。
このscriptのSTEPSが**唯一の正本**。新しい生成器を足す時はここに足す(skillには足さない)。

  python scripts/_weekly-step1.py                 # 全step順次実行(失敗で即exit 1)
  python scripts/_weekly-step1.py --from shinkan  # 途中から再開
  python scripts/_weekly-step1.py --skip tameshiyomi-harvest,tameshiyomi-expand  # 明示skip
  python scripts/_weekly-step1.py --list          # 計画表示のみ

特殊step:
  - calendar-prod/preview: <当月YYYY-MM> はJSTで自動導出
  - cover-refresh: 終了後 .cache/cover-refresh-touched.txt が非空なら
    promote --only-file を自動連鎖(差し替え書影を頁へ反映してから索引を焼く)
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
YM = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m")

# (name, argv, 説明)。順序=依存順(カレンダー→書影refresh→shinkan、索引は最後)。
STEPS = [
    ("calendar-prod",     ["_build-calendar.py", "data/manga.v2", "data/calendar", YM],
     "本番フルカレンダー(r2-syncがoverlay。引数なし実行=preview先に書く事故の根絶)"),
    ("calendar-preview",  ["_build-calendar.py", ".preview-data/manga", "public/calendar", YM],
     "previewカレンダー(src=preview自身)"),
    ("cover-refresh",     ["_cover-release-refresh.py", "--days", "45"],
     "発売後の書影差し替え追従(~40分。touched非空→promote自動連鎖)"),
    ("shinkan",           ["_gen-shinkan-data.py"],
     "/shinkan 月別データ(カレンダー・書影refreshの後)"),
    ("corner-stocks",     ["_gen-corner-stocks.py"], "三世代/featured stock"),
    ("daily-feature",     ["_gen-daily-feature.py"], "日替わり特集stock補充(既存日は凍結)"),
    ("corner-auto",       ["_gen-corner-auto.py"], "周年/豪華版 JSON(66k走査 ~5分)"),
    ("tameshiyomi-harvest", ["_tameshiyomi-harvest.py", "--limit", "100"],
     "試し読み新規アンカー発見(TinyFish ~100検索)"),
    ("tameshiyomi-expand", ["_tameshiyomi-harvest.py", "--expand", "--expand-limit", "300"],
     "新規アンカーの全巻展開(残はアイドル運転が消化)"),
    ("tameshiyomi-map",   ["_gen-tameshiyomi-map.py"], "試し読みマップ(blmax反映 ~2秒)"),
    ("tameshiyomi-ln",    ["_audit-tameshiyomi-ln.py"],
     "LN混入検査(領民0人型。flag増=誤アンカー→差替)"),
    ("anilist-status",    ["_gen-anilist-status-map.py"],
     "AniList statusマップ(連載中→完結降格の鮮度維持)"),
    ("placeholder-queue", ["_placeholder-cover-refresh.py", "--build-queue"],
     "書影queue週次再算出(消化=アイドル運転⑩)"),
    ("list-index",        ["_build-list-index.py", "data/manga.v2", "data"],
     "本番索引(~10分。★必ず最後=上のstepの変更を焼き込む)"),
]


def run_step(name: str, argv: list[str]) -> None:
    t0 = time.time()
    print(f"\n{'=' * 70}\n▶ [{name}] {' '.join(argv)}\n{'=' * 70}", flush=True)
    r = subprocess.run([PY, str(ROOT / "scripts" / argv[0])] + argv[1:], cwd=str(ROOT))
    if r.returncode != 0:
        print(f"\n✗ ABORT: step [{name}] failed (exit {r.returncode})。"
              f"直してから `--from {name}` で再開。")
        sys.exit(r.returncode or 1)
    print(f"✓ [{name}] done ({time.time() - t0:.0f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_step", default=None, help="このstepから再開")
    ap.add_argument("--skip", default="", help="カンマ区切りで明示skip")
    ap.add_argument("--list", action="store_true", help="計画表示のみ")
    a = ap.parse_args()
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    names = [n for n, *_ in STEPS]
    for bad in skip | ({a.from_step} if a.from_step else set()):
        if bad and bad not in names:
            print(f"ABORT: 不明なstep名 {bad} (候補: {', '.join(names)})")
            sys.exit(1)

    started = a.from_step is None
    plan = []
    for name, argv, desc in STEPS:
        if not started:
            started = name == a.from_step
        if started and name not in skip:
            plan.append((name, argv, desc))
    print(f"週次 手順1 事前再生成 (当月={YM} / {len(plan)}/{len(STEPS)} step)")
    for name, argv, desc in plan:
        print(f"  [{name:<19}] {desc}")
    if a.list:
        return

    for name, argv, desc in plan:
        run_step(name, argv)
        if name == "cover-refresh":
            touched = ROOT / ".cache" / "cover-refresh-touched.txt"
            slugs = [l for l in touched.read_text(encoding="utf-8").splitlines() if l.strip()] \
                if touched.exists() else []
            if slugs:
                run_step("cover-refresh-promote",
                         ["_promote-bulk-v2.py", "--only-file", str(touched)])
                print(f"  (書影差し替え {len(slugs)} 頁を再生成)")

    print(f"\n{'=' * 70}\n✓ 手順1 完了。次: 生成物commit+push → art-books昇格diff確認 → "
          f"python scripts/_weekly-preflight.py --fix")


if __name__ == "__main__":
    main()
