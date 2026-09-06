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

# ★2026-09-06 ユーザ裁定「BookLive!は憶測でかけるはず。試す必要なし」:
#   試し読みURLは保存しておらず **title_id + 巻番号(3桁0詰め)** から client が組み立てる
#   (components/VolumeCoverflow の `bviewer/s/?cid=<tid>_<vol>`)。つまりリンクを**作るのに検証は要らない**。
#   HEAD検証は「ボタンをどこまで出すか」を決めるためだけのもので、その検証が2026-08-29の
#   278万リクエスト規制事故を生んだ([[booklive_access_incident]])。しかも規制中は
#   **正解の巻すら403**を返すので検証自体が成立しない(2026-09-06に3件で実測)。
#   → 末尾は**本番頁の巻数まで構築で伸ばす**。検証済みの範囲内の穴(missing)だけは
#     サイトが健全だった時期の実測なのでそのまま残す。
_pagemax = {}
try:
    _idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    _f = {k: i for i, k in enumerate(_idx["f"])}
    for _r in _idx["d"]:
        _pagemax[_r[_f["slug"]]] = _r[_f["max_edition_volumes"]] or 0
except Exception:
    pass

out = {}
n_miss = 0
n_ext = 0
n_extvol = 0
for slug, tid in anchors.items():
    vs = vols.get(slug) or {1}   # アンカー時点で _001 はHEAD200済み
    mx = max(vs)
    missing = [n for n in range(1, mx + 1) if n not in vs]
    _pm = _pagemax.get(slug, 0)
    if _pm > mx:
        n_ext += 1
        n_extvol += _pm - mx
        mx = _pm
    if missing:
        n_miss += 1
        out[slug] = [tid, mx, missing]
    else:
        out[slug] = [tid, mx]

json.dump(out, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
sz = os.path.getsize(OUT) / 1024
print(f"tameshiyomi-map: {len(out):,}作 (missing持ち{n_miss}) → {OUT} ({sz:.0f}KB)")
print(f"  ★構築で末尾を延長: {n_ext:,}作品 / {n_extvol:,}巻(検証せずtitle_id+巻番号で組む)")
