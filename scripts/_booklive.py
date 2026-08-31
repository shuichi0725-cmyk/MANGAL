#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookLive宛アクセスの共通ゲート (= 2026-08-31 新設。規約の実装正本)

2026-08-29 のアクセス規制事故(無限ループ+8並列で231万リクエスト)の再発防止で制定した
「BookLiveアクセス規約」を、BookLiveを叩く**全script**に1箇所で効かせる共通層。
規約の文書正本 = skill tameshiyomi-harvest の「BookLiveアクセス規約」節。
★BookLive宛の urlopen をこのモジュールを通さずに書かない(コピペで別ペーサを作らない。
  _rate_gate.py と同じ原則)。並列化も禁止(ゆるめる時はユーザ裁定)。

保証すること:
  ① 停止札(BOOKLIVE-BLOCKED.md / .cache/tameshiyomi/BLOCKED)があれば1リクエストも出さず SystemExit
  ② _rate_gate("booklive", 2.0) でプロセス間直列化(何本並走してもhost単位で1本のストリーム)
  ③ 上限 = 1実行 MAX_REQ_PER_RUN 件 / 1日 MAX_REQ_PER_DAY 件(プロセス間)。
     到達は CapReached = **正常な打ち切り**(呼び手はexit 0で終わり次回に続き。★停止札は置かない)
  ④ 200/404 以外(429/403/5xx/timeout/接続断)は Blocked = 呼び手は**台帳に書かずに即中断(exit 2)**
     = 「規制されている」を「無い」と誤記録して偽404を永久固定しない(事故の最悪副作用)
  ⑤ UA は正直な MangalBot(連絡先付き)。Mozilla偽装をしない

使い方(BookLive宛の全リクエスト):
    import _booklive
    from _booklive import Blocked, CapReached
    st, html = _booklive.request(url)            # GET。200=(200,本文) / 404=(404,None) / 他=Blocked
    ok = _booklive.head200(url)                  # HEAD。True=200 / False=404 / 他=Blocked
呼び手の except は必ず2種を分ける:
    except CapReached: 正常打ち切り(逐次保存済みを報告して exit 0)
    except Blocked:    台帳に書かず exit 2 (= ループ/週次が停止札を置く)
"""
import json
import os
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQ_INTERVAL = 2.0          # 秒/リクエスト(直列)。NDLの1.3秒より保守的
MAX_REQ_PER_RUN = 1500      # 1実行あたりの上限
MAX_REQ_PER_DAY = 5000      # 1日あたりの上限(プロセスをまたいで数える)
UA = "MangalBot/1.0 (+https://mangal.shuichi0725.workers.dev; contact shuichi0725@gmail.com)"
DAYCOUNT = os.path.join(ROOT, ".cache", "tameshiyomi", "booklive-daycount.json")
BLOCK_FLAGS = (os.path.join(ROOT, "docs", "production-diagnostics", "BOOKLIVE-BLOCKED.md"),
               os.path.join(ROOT, ".cache", "tameshiyomi", "BLOCKED"))
_req_count = [0]


class Blocked(Exception):
    """規制/障害が疑われる応答。台帳に書かずに即中断(exit 2)するための例外。"""


class CapReached(Exception):
    """1実行/1日の上限に到達。★規制ではない=正常な打ち切り(exit 0・停止札は置かない)。
    旧実装は日次上限も Blocked にしていたため、上限到達→exit 2→ループが停止札を置き
    ユーザ介入まで柱が凍る誤動作があった(2026-08-31 是正)。"""


def req_count():
    """この実行でBookLiveへ送った件数。"""
    return _req_count[0]


def assert_not_blocked():
    """★停止札があるうちは1リクエストも出さない(規制中の再突入防止)。
    各scriptの入口でも呼ぶ=TinyFish検索や重い前処理を始める前に落とす。"""
    for f in BLOCK_FLAGS:
        if os.path.exists(f):
            raise SystemExit(
                "停止札あり(%s) = BookLive規制中。リクエストを出さずに終了する。\n"
                "解除はユーザが『復帰した』と言った時だけ。手順は札の中身。" % os.path.relpath(f, ROOT))


def _day_bump():
    """日次カウンタ(プロセス間)。上限超えは CapReached(正常打ち切り)。"""
    today = time.strftime("%Y-%m-%d")
    d = {"date": today, "n": 0}
    try:
        d = json.load(open(DAYCOUNT, encoding="utf-8"))
        if d.get("date") != today:
            d = {"date": today, "n": 0}
    except Exception:
        pass
    d["n"] = int(d.get("n") or 0) + 1
    try:
        os.makedirs(os.path.dirname(DAYCOUNT), exist_ok=True)
        json.dump(d, open(DAYCOUNT, "w", encoding="utf-8"))
    except OSError:
        pass
    if d["n"] > MAX_REQ_PER_DAY:
        raise CapReached("1日の上限%d件に到達(明日以降に回す)" % MAX_REQ_PER_DAY)


def throttle():
    """全BookLiveリクエストの直前に1回。札→SystemExit / 上限→CapReached / レート→sleep。"""
    if _req_count[0] + 1 > MAX_REQ_PER_RUN:
        raise CapReached("1実行の上限%d件に到達(続きは次回)" % MAX_REQ_PER_RUN)
    assert_not_blocked()
    _day_bump()
    try:
        import _rate_gate
        _rate_gate.wait("booklive", REQ_INTERVAL)
    except (Blocked, CapReached):
        raise
    except Exception:
        time.sleep(REQ_INTERVAL)
    _req_count[0] += 1


def request(url, method="GET", timeout=30):
    """→ (status, text)。 200=(200, 本文str[HEADは""]) / 404=(404, None)。
    ★その他(429/403/5xx/timeout/接続断)は Blocked = 呼び手は台帳に書かずに即中断する。"""
    throttle()
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = "" if method == "HEAD" else r.read().decode("utf-8", "ignore")
            return r.status, body
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, None        # ★これだけが「本当に無い」
        raise Blocked(f"HTTP {e.code} {url}")
    except Exception as e:
        raise Blocked(f"{type(e).__name__} {url}")


def head200(url, timeout=20):
    """HEADで存否だけ。 True=200 / False=404。 その他は Blocked。"""
    st, _ = request(url, method="HEAD", timeout=timeout)
    return st == 200
