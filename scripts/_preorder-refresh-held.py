# -*- coding: utf-8 -*-
"""保留頁の自動再訪 (2026-08-24 ユーザGO③)。

demographic/caption 未供給で索引保留になった予約由来頁(発売直後は楽天が空=正常)を、
後日の日次で自動再照会して埋める。捏造はしない=楽天が返した時だけ埋まる。

対象 = data/seeds/preorder-pages/*.yml のうち demographic 空 or rakuten_caption 空。
照会 = 楽天 live by ISBN(rakuten_live_retry・1.3s)。booksGenreId→demographic 写像は分類器と同じ。
更新 = preorder-pages(恒久保管庫) を直接更新 → 変更slugを表示(呼び手が reflect --only する)。

usage: python scripts/_preorder-refresh-held.py [--limit 30]
"""
import argparse
import glob
import io
import os
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib
_LK = importlib.import_module("_lookup")

# 分類器と同じ写像(booksGenreId 3階層目まで)
DEMO_MAP = {"001001": "shounen", "001002": "shoujo", "001003": "seinen",
            "001004": "josei", "001021": "josei"}


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
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    env = load_env()
    touched = []
    n_seen = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "seeds", "preorder-pages", "*.yml"))):
        y = yaml.safe_load(io.open(f, encoding="utf-8")) or {}
        need_demo = not y.get("demographic")
        need_cap = not (y.get("rakuten_caption") or y.get("synopsis"))
        if not (need_demo or need_cap):
            continue
        isbn = None
        for ed in y.get("editions") or []:
            for v in ed.get("volumes") or []:
                if v.get("isbn13"):
                    isbn = str(v["isbn13"])
                    break
            if isbn:
                break
        if not isbn:
            continue
        if n_seen >= a.limit:
            break
        n_seen += 1
        try:
            items = _LK.rakuten_live_retry(env, isbn=isbn)
        except Exception as e:
            print("  ERR", y.get("slug"), type(e).__name__, flush=True)
            continue
        it = (items or [{}])[0]
        it = it.get("Item") or it
        changed = []
        gid = str(it.get("booksGenreId") or "")
        if need_demo:
            for g in gid.split("/"):
                d = DEMO_MAP.get(g[:6])
                if d:
                    y["demographic"] = d
                    changed.append(f"demographic={d}")
                    break
        cap = (it.get("itemCaption") or "").strip()
        if need_cap and len(cap) > 20:
            y["rakuten_caption"] = cap
            changed.append("caption")
        if changed:
            io.open(f, "w", encoding="utf-8", newline="\n").write(
                yaml.safe_dump(y, allow_unicode=True, sort_keys=False))
            touched.append(os.path.basename(f)[:-4])
            print(f"  更新 {y.get('slug')}: {'+'.join(changed)}", flush=True)
        time.sleep(1.3)
    print(f"再訪 {n_seen} / 更新 {len(touched)}")
    if touched:
        print("→ 反映: python scripts/_reflect-targeted.py --only " + ",".join(touched) + " --commit-only")


if __name__ == "__main__":
    main()
