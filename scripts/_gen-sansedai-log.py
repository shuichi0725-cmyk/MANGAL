#!/usr/bin/env python3
"""三世代/今日の一冊: 日別picksの凍結ログ(= 一度表示した日は永久固定。2026-07-30 ユーザ裁定)。

- 出力: public/data/sansedai-log.json = {"YYYY-MM-DD": [{persona,gen,slug,title,comment,cover}×3]}
- 現stock(public/data/sansedai-stock.json) + ホームと同一式(picksForDay) で
  2026-06-01(コーナー開始日) .. **昨日**(JST) のうち **未凍結の日だけ** を追記。
  (★今日は凍結しない: 表示進行中の日をstock改版直前に固めるとホームとズレる。
   完結した日だけを、その日を表示していたstockで固定する)
- ★既存日付は絶対に上書きしない(純粋追加)。stockが改版されても過去日は変わらない。
- ★実行順序が命: stock再生成(_gen-corner-stocks.py)の**前**に走らせる
  (= 旧stockで実際に表示された日を、旧stockのまま固定するため。生成器側に組込済)。
- 単独実行も可(アイドル時に叩けば当日分が凍結される): python scripts/_gen-sansedai-log.py
"""
import json, os, sys
from datetime import datetime, timezone, timedelta, date

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK = os.path.join(ROOT, "public", "data", "sansedai-stock.json")
LOG = os.path.join(ROOT, "public", "data", "sansedai-log.json")
EPOCH = date(2026, 6, 1)  # コーナー開始日(これ以前は凍結しない)
UNIX = date(1970, 1, 1)


def day_index(d: date) -> int:
    """クライアントの jstDayIndex と同一値 (= floor((now+9h)/86400000) の日付版)。"""
    return (d - UNIX).days


def picks_for_day(stock: list, day: int) -> list:
    """components/SansedaiDaily.tsx picksForDay と同一式。"""
    out = []
    for g in (0, 1, 2):
        pool = [e for e in stock if int(e.get("gen", -1)) == g]
        if not pool:
            continue
        out.append(pool[day % len(pool)])
    return out


def main():
    if not os.path.exists(STOCK):
        print("sansedai-stock.json が無いので凍結skip(初回build前)")
        return
    stock = json.load(open(STOCK, encoding="utf-8"))
    if not stock:
        print("stock空のため凍結skip")
        return
    log = {}
    if os.path.exists(LOG):
        log = json.load(open(LOG, encoding="utf-8"))
    before = len(log)
    yesterday = datetime.now(timezone(timedelta(hours=9))).date() - timedelta(days=1)
    d = EPOCH
    added = 0
    while d <= yesterday:
        key = d.isoformat()
        if key not in log:  # ★純粋追加。既存日は不変
            picks = picks_for_day(stock, day_index(d))
            if picks:
                log[key] = picks
                added += 1
        d += timedelta(days=1)
    if added == 0:
        print(f"凍結追加なし(既存 {before}日分)")
        return
    ordered = {k: log[k] for k in sorted(log)}
    json.dump(ordered, open(LOG, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"sansedai-log.json: 既存{before}日 + 追記{added}日 = {len(ordered)}日分 (上書き0)")


if __name__ == "__main__":
    main()
