#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prod-pages-manifest 初期化 (= 差分反映エンジンの検出基準点。週次蒸留の直後に実行)

manifest = 「本番R2に居る頁の yml ハッシュ」。以後の変更が diff として検出される。
--cutoff "YYYY-MM-DD HH:MM" 指定時: それ以降に変更された yml は manifest から除外
(= まだ本番に出ていない変更として即 diff 扱いにする。初期化を後追いでやる時用)。
"""
import argparse, glob, hashlib, json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PM = os.path.join(ROOT, ".cache", "prod-pages-manifest.json")

ap = argparse.ArgumentParser()
ap.add_argument("--cutoff", help='この時刻(ローカル "YYYY-MM-DD HH:MM")以降のmtimeは未デプロイ扱いで除外')
a = ap.parse_args()
cut = time.mktime(time.strptime(a.cutoff, "%Y-%m-%d %H:%M")) if a.cutoff else None

pm, skipped = {}, 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    if cut and os.path.getmtime(p) >= cut:
        skipped += 1
        continue
    pm[os.path.basename(p)[:-4]] = hashlib.sha1(open(p, "rb").read()).hexdigest()[:16]
json.dump(pm, open(PM, "w"))
print(f"manifest初期化: {len(pm):,}頁 (未デプロイ扱い除外 {skipped}) → {PM}")
