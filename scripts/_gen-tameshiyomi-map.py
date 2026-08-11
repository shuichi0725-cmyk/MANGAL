# -*- coding: utf-8 -*-
"""試し読みマップ生成 (= 2026-08-06 全結線。週次蒸留の事前再生成で毎回実行)

data/seeds/tameshiyomi-booklive.jsonl(アンカー=slug×title_id) と
data/seeds/tameshiyomi-booklive-volumes.jsonl(HEAD検証済み巻) から、
ビルド時join用の compact map を生成する:

  data/tameshiyomi-map.json = { slug: [title_id, max_verified_vol, [missing...]] }

- max = 検証済み巻の最大値。missing = 1..max のうち未検証(404等)の巻(大半は空)。
- 表示側(components/VolumeCoverflow)は 選択巻<=max かつ not in missing でボタンを出す。
- URLは保存しない(title_id+巻番号からクライアントで組む=容量最小)。
"""
import gzip
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl")
VOLSEED = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive-volumes.jsonl.gz")
OUT = os.path.join(ROOT, "data", "tameshiyomi-map.json")

anchors = {}
for ln in io.open(SEED, encoding="utf-8"):
    d = json.loads(ln)
    anchors[d["slug"]] = str(d["title_id"])

vols = {}
for ln in gzip.open(VOLSEED, "rt", encoding="utf-8"):
    d = json.loads(ln)
    vols.setdefault(d["slug"], set()).add(int(d["volume"]))

out = {}
n_miss = 0
for slug, tid in anchors.items():
    vs = vols.get(slug) or {1}   # アンカー時点で _001 はHEAD200済み
    mx = max(vs)
    missing = [n for n in range(1, mx + 1) if n not in vs]
    if missing:
        n_miss += 1
        out[slug] = [tid, mx, missing]
    else:
        out[slug] = [tid, mx]

json.dump(out, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
sz = os.path.getsize(OUT) / 1024
print(f"tameshiyomi-map: {len(out):,}作 (missing持ち{n_miss}) → {OUT} ({sz:.0f}KB)")
