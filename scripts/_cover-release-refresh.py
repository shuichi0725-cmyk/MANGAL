# -*- coding: utf-8 -*-
"""発売後の書影差し替え追従 (2026-08-25 ユーザ発見: 発売済み30冊中14冊=47%が旧書影)。

型: 楽天は発売前後に画像を更新し、URL末尾の版数が上がる(_1_7.jpg→_1_9.jpg)か
.gif仮書影→実jpgになる。うちは収穫時URLで凍結していた(仮書影検出器は.gif型しか見ない)。

処理: 直近 --days 日以内に発売された巻(ISBN有り)を楽天live再照会し、
現在のURLと異なれば cover-override.jsonl へ追記(ノーマライズ比較・noimage除外)。
→ 対象頁を promote --only-file で再生成(このscriptはリスト出力まで)。
週次蒸留のstep1で --days 45 を回す。

usage: python scripts/_cover-release-refresh.py [--days 45] [--limit 0=無制限]
"""
import argparse
import datetime
import glob
import io
import json
import os
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib
_LK = importlib.import_module("_lookup")


def load_env():
    env = {}
    for name in (".env.local", ".env"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            for ln in io.open(p, encoding="utf-8"):
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--from", dest="lo", default=None, help="期間指定 YYYY-MM-DD(--daysより優先。未来も可=予約書影も動く)")
    ap.add_argument("--to", dest="hi", default=None)
    a = ap.parse_args()
    today = datetime.date.today()
    lo = a.lo or (today - datetime.timedelta(days=a.days)).isoformat()
    hi = a.hi or today.isoformat()

    # 直近発売巻の収集(発売日がlo..hi・ISBN有り)
    targets = []  # (slug, isbn, cur_cover)
    for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        t = io.open(f, encoding="utf-8").read()
        if lo[:4] not in t and hi[:4] not in t:
            continue
        try:
            y = yaml.safe_load(t)
        except Exception:
            continue
        stem = os.path.basename(f)[:-4]
        for ed in y.get("editions") or []:
            for v in ed.get("volumes") or []:
                d = str(v.get("release_date") or "")[:10]
                if len(d) == 10 and lo <= d <= hi and v.get("isbn13"):
                    targets.append((stem, str(v["isbn13"]), str(v.get("cover_url") or "")))
    print(f"対象巻(発売{lo}〜{hi}): {len(targets)}", flush=True)
    if a.limit:
        targets = targets[: a.limit]

    env = load_env()
    out = io.open(os.path.join(ROOT, "data", "seeds", "cover-override.jsonl"), "a", encoding="utf-8", newline="\n")
    touched = set()
    n_upd = n_same = n_none = n_err = 0
    for i, (stem, isbn, cur) in enumerate(targets):
        try:
            items = _LK.rakuten_live_retry(env, isbn=isbn)
        except Exception:
            n_err += 1
            continue
        live = ""
        for it in items or []:
            d = it.get("Item") or it
            live = d.get("largeImageUrl") or d.get("mediumImageUrl") or ""
            if live:
                break
        if not live or "noimage" in live:
            n_none += 1
        elif live.split("?")[0] == cur.split("?")[0]:
            n_same += 1
        else:
            url = live.replace("?_ex=120x120", "?_ex=300x300").replace("?_ex=200x200", "?_ex=300x300")
            out.write(json.dumps({"isbn13": isbn, "cover_url": url, "slug": stem,
                                  "reason": f"発売後差し替え追従(旧:{cur.split('/')[-1][:28]})",
                                  "at": today.isoformat()}, ensure_ascii=False) + "\n")
            out.flush()
            touched.add(stem)
            n_upd += 1
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(targets)} 更新{n_upd}", flush=True)
        time.sleep(1.3)
    io.open(os.path.join(ROOT, ".cache", "cover-refresh-touched.txt"), "w", encoding="utf-8", newline="\n").write(
        "\n".join(sorted(touched)))
    print(f"更新{n_upd} / 同一{n_same} / 楽天無し{n_none} / err{n_err} → 対象頁 {len(touched)}")
    if touched:
        print("→ 再生成: python scripts/_promote-bulk-v2.py --only-file .cache/cover-refresh-touched.txt")


if __name__ == "__main__":
    main()
