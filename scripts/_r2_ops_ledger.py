# -*- coding: utf-8 -*-
"""R2 Class A 使用量の簿記(共通モジュール。2026-08-26 ユーザ裁定「週次は絶対毎週やる=事故防止」)。

- Class A = PUT + LIST(DELETEはR2無料)。無料枠 1,000,000/月(27日〆)。
- 書込経路は3本のみ(grep実証): _r2-sync / _deploy-differential / _deploy-feature。全部これを呼ぶ。
- 台帳: data/seeds/r2-ops-ledger.jsonl(git追跡=別PCでも累計が生きる)
"""
import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "data", "seeds", "r2-ops-ledger.jsonl")
FREE_TIER = 1_000_000
FULL_WEEK_COST = 190_000  # 全頁週の実測(18.5万PUT+LIST等)の丸め


def period_start(today=None):
    """課金期間の起点(27日〆: 7/27-8/26 → 起点7/27)。"""
    t = today or datetime.date.today()
    if t.day >= 27:
        return t.replace(day=27)
    return (t.replace(day=1) - datetime.timedelta(days=1)).replace(day=27)


def record(put: int, list_ops: int, source: str) -> None:
    with open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "source": source, "put": int(put), "list": int(list_ops),
                            "class_a": int(put) + int(list_ops)}) + "\n")


def period_total(today=None) -> int:
    start = period_start(today).isoformat()
    total = 0
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8"):
            try:
                r = json.loads(ln)
                if r.get("at", "")[:10] >= start:
                    total += int(r.get("class_a") or 0)
            except Exception:
                pass
    return total


def projection(today=None):
    """(今期累計, 期末までの残り週次回数, 全頁週前提の着地見込み)"""
    t = today or datetime.date.today()
    start = period_start(t)
    # ★期末=翌月27日。旧 `start+35日→replace(27)` は 8月(31日)+9月(30日)等で月を2つ跨ぎ
    #   期末が1ヶ月先に化けて「あと8回」と倍の悲観推計を出していた(2026-08-31 ユーザ指摘で実踏)。
    #   day=1 に戻して+32日なら必ず翌月に着地する。
    end = (start.replace(day=1) + datetime.timedelta(days=32)).replace(day=27)
    used = period_total(t)
    weeks_left = max(0, ((end - t).days) // 7)
    return used, weeks_left, used + weeks_left * FULL_WEEK_COST


def report(today=None) -> str:
    used, wl, proj = projection(today)
    line = (f"R2 Class A: 今期累計 {used:,} / 枠 {FREE_TIER:,} | 期末まで週次あと{wl}回 "
            f"→ 全頁週前提の着地見込み {proj:,}")
    if proj > FREE_TIER:
        line += "  ★★超過見込み(全頁週=UI共通部の変更週を1回スキップ/隔週化すれば収まる)"
    return line
