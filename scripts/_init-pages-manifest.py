#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prod-pages-manifest 初期化 (= 差分反映エンジンの検出基準点。週次蒸留の直後に実行)

manifest = 「本番R2に居る頁の yml ハッシュ」。以後の変更が diff として検出される。
--cutoff "YYYY-MM-DD HH:MM" 指定時: それ以降に変更された yml は manifest から除外
(= まだ本番に出ていない変更として即 diff 扱いにする。初期化を後追いでやる時用)。

★併せて `prod-page-slugs.json`(stem → 公開slug)も書く (2026-09-04)。
  manifest のキーは **SRC stem** で、公開URLの slug とは 1,759頁/69,223頁 で食い違う
  ([[pubslug_src_stem_generator_trap]])。 頁を消した後は yml が無く slug を引けないため、
  「消える前の対応表」をここで残しておかないと、差分反映の **purge と IndexNow の削除通知が
  存在しないURLに飛ぶ**(= 本物の旧URLは通知されない)。
"""
import argparse, glob, hashlib, json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PM = os.path.join(ROOT, ".cache", "prod-pages-manifest.json")
SLUGS = os.path.join(ROOT, ".cache", "prod-page-slugs.json")
SLUG_RE = re.compile(rb"^slug:\s*(.+?)\s*$", re.M)

ap = argparse.ArgumentParser()
ap.add_argument("--cutoff", help='この時刻(ローカル "YYYY-MM-DD HH:MM")以降のmtimeは未デプロイ扱いで除外')
a = ap.parse_args()
cut = time.mktime(time.strptime(a.cutoff, "%Y-%m-%d %H:%M")) if a.cutoff else None

pm, slugs, skipped = {}, {}, 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    if cut and os.path.getmtime(p) >= cut:
        skipped += 1
        continue
    st = os.path.basename(p)[:-4]
    raw = open(p, "rb").read()
    pm[st] = hashlib.sha1(raw).hexdigest()[:16]
    m = SLUG_RE.search(raw)
    sl = m.group(1).decode("utf-8", "replace").strip().strip('"').strip("'") if m else ""
    if sl and sl != st:            # 同じものは持たない(既定=stem。 台帳は例外だけで十分)
        slugs[st] = sl
json.dump(pm, open(PM, "w"))
json.dump(slugs, open(SLUGS, "w"))
print(f"manifest初期化: {len(pm):,}頁 (未デプロイ扱い除外 {skipped}) → {PM}")
print(f"公開slug台帳: stem≠slug の {len(slugs):,}頁 → {SLUGS}")
