#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""プロセス間グローバル・レートゲート (= 2026-07-24 新設)

背景: 楽天/NDL は「per-プロセスで1.3s」を守っても、複数のアイドル柱
(⑦ voldesc-material / ⑧ kana-digit-harvest 等)が同じ app-id・同じ IP から
並走すると、host 側は合算レートで見るため上限(~1req/s/app)を超えて即429になる。
wiki は _wiki_host.py の排他ロックで直列化したが、楽天/NDL には同等機構が無かった。

このゲートを「楽天/NDL 呼出の直前」に通すと、柱が何本並走しても host 単位で
interval 秒の単一ストリームに直列化される。 ★予約制: ロック保持は µ秒(状態の
read-modify-write のみ)、実際の待ちは sleep でロック外に出す=デッドロックしない。

使い方(呼出の直前に1回):
    import _rate_gate
    _rate_gate.wait("rakuten", 1.3)
    # ... urlopen(...) ...

正本はここ。 楽天/NDL を叩く全実装(_lookup.rakuten_live / ndl_live、
_voldesc-material.live_item 等)はこのゲートを経由すること=コピペで別ペーサを作らない。
"""
import json, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")


def _paths(host):
    base = os.path.join(CACHE, f"rategate-{host}")
    return base + ".json", base + ".lock"


def _acquire(lockpath, timeout=15.0):
    """短時間の排他ロック(O_EXCL)。 臨界区間は µ秒。 30s超のstaleは残骸として奪う。
    取れなくても最終的には進む(最悪でも従来の per-proc pacing に劣化するだけ)。"""
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(lockpath, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lockpath) > 30:
                    os.remove(lockpath)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                return False
            time.sleep(0.02)
        except OSError:
            return False


def _release(lockpath):
    try:
        os.remove(lockpath)
    except OSError:
        pass


def wait(host, interval):
    """host 単位のグローバル間隔を予約し、自分の番までsleepする(プロセス間で有効)。"""
    try:
        os.makedirs(CACHE, exist_ok=True)
    except OSError:
        pass
    statepath, lockpath = _paths(host)
    got = _acquire(lockpath)
    try:
        nxt = 0.0
        try:
            nxt = float(json.load(open(statepath, encoding="utf-8")).get("next", 0))
        except Exception:
            nxt = 0.0
        now = time.time()
        fire = max(now, nxt)
        try:
            json.dump({"next": fire + interval, "at": now}, open(statepath, "w", encoding="utf-8"))
        except OSError:
            pass
    finally:
        if got:
            _release(lockpath)
    delay = fire - time.time()
    if delay > 0:
        time.sleep(delay)


if __name__ == "__main__":
    import sys
    h = sys.argv[1] if len(sys.argv) > 1 else "rakuten"
    sp, _ = _paths(h)
    try:
        d = json.load(open(sp, encoding="utf-8"))
        left = d.get("next", 0) - time.time()
        print(f"{h}: next slot in {max(0, left):.2f}s (state={sp})")
    except Exception:
        print(f"{h}: no state yet ({sp})")
