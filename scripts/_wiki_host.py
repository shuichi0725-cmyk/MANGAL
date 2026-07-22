#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wikipediaホストの排他ロック+429冷却タイマー (= 2026-07-24 新設)

背景: アイドル運転⑤(wiki-fetch)と⑧(kana-digit-harvest)が同ホストを叩く。
運転者(Sonnet)に「同時起動するな」「429なら1時間待て」の判断をさせない:
 - 同時起動 → 後発が即exit(3)するだけ=起動してよい
 - 429 → 冷却をファイルに焼く。冷却中の再起動も即exit(3)=待機・調査は不要、他の柱へ

使い方(両scriptで):
    from _wiki_host import cooldown_check, cooldown_set, acquire, release
    cooldown_check(); acquire("wiki-fetch")   # 開始時
    cooldown_set(60)                          # 429を受けた時(そのままexit 2してよい)
    release("wiki-fetch")                     # 正常終了/中断時(finally推奨)
"""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, ".cache", "wiki-host.lock")
COOL = os.path.join(ROOT, ".cache", "wiki-host-cooldown.json")
STALE_SEC = 2 * 3600  # これより古いロックは残骸とみなし奪う


def cooldown_check():
    """冷却中なら即exit(3)。運転者は待たずに他の柱へ(scriptが明ける時を判断する)。"""
    if not os.path.exists(COOL):
        return
    try:
        d = json.load(open(COOL, encoding="utf-8"))
        left = int(d.get("until", 0) - time.time())
    except Exception:
        return
    if left > 0:
        print(f"★wiki冷却中(あと{left // 60 + 1}分, 起因={d.get('by', '?')}) → このバッチはskip。"
              f"待機禁止=他の柱を回す。冷却明けは再起動すれば自動で通る")
        sys.exit(3)
    try:
        os.remove(COOL)
    except OSError:
        pass


def cooldown_set(minutes=60, by="wiki"):
    os.makedirs(os.path.dirname(COOL), exist_ok=True)
    json.dump({"until": time.time() + minutes * 60, "by": by, "at": time.time()},
              open(COOL, "w", encoding="utf-8"))
    print(f"★429 → wiki冷却{minutes}分を記録。待機・調査は不要=他の柱へ(再起動は冷却明けに自動で通る)")


def acquire(name):
    """ホスト占有。他者が保持中(2h以内)なら即exit(3)=同時起動しても無害。"""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    if os.path.exists(LOCK):
        try:
            d = json.load(open(LOCK, encoding="utf-8"))
        except Exception:
            d = {}
        age = time.time() - float(d.get("at", 0))
        if d.get("name") not in (None, name) and age < STALE_SEC:
            print(f"★wikiホスト使用中({d.get('name')}, {int(age // 60)}分前から) → このバッチはskip。"
                  f"待機禁止=他の柱を回す(使用側が終われば自動で通る)")
            sys.exit(3)
    json.dump({"name": name, "pid": os.getpid(), "at": time.time()}, open(LOCK, "w", encoding="utf-8"))


def release(name):
    try:
        d = json.load(open(LOCK, encoding="utf-8"))
        if d.get("name") == name:
            os.remove(LOCK)
    except Exception:
        pass
