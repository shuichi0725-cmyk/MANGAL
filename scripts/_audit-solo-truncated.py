#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""単巻切り詰め検出(solo_nonfirst型) = 「1冊しか無いのに巻番号が2以上」の頁を全DB走査。

背景(2026-07-03 ユーザ要望): シャイナ・ダルク(v3のみ)/グリードパケット∞(v4のみ)/
不測ノ恋情(v3のみ)/Bite Maker断片(v7のみ) の型は巻抜け(gap)検出に出ない
(= 1冊では範囲が無く欠番を計算できない)ため専用検出器が要る。

分類:
 - DUP_ELSEWHERE: そのISBNが他頁でも描画中 = 断片重複(Bite Maker型) → dedup候補(最有力)
 - CACHE_SIBLINGS: 楽天題キャッシュに同題の別巻が居る = 切り詰め濃厚(シャイナ・ダルク型)
 - NO_EVIDENCE: 続巻証拠なし = 電子先行の紙化(不測ノ恋情型=1-2巻電子限定)や
   シリーズ通番の単発紙化がありうる → ★自動fill禁止・per-case(NDL/Wiki確認)

出力: docs/production-diagnostics/solo-truncated.tsv
使い方: python scripts/_audit-solo-truncated.py
"""
import glob, json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "solo-truncated.tsv")

def norm_title(t):
    t = re.sub(r"[\s　〜~！!?？・:：（）()【】\[\]「」『』]", "", str(t or ""))
    return t.lower()

# ISBN→頁 索引(断片重複判定)
iidx_p = os.path.join(ROOT, ".cache", "isbn-page-index.json")
iidx = json.load(open(iidx_p, encoding="utf-8")) if os.path.exists(iidx_p) else {}

# 楽天題キャッシュ(続巻証拠)
tm_p = os.path.join(ROOT, ".cache", "isbn-title-map.json")
tm = json.load(open(tm_p, encoding="utf-8")) if os.path.exists(tm_p) else {}
by_title = {}
for ib, t in tm.items():
    m = re.search(r"[（(](\d{1,3})[)）]\s*$", t)
    base = norm_title(re.sub(r"[（(]\d{1,3}[)）]\s*$", "", t))
    if base and m:
        by_title.setdefault(base, set()).add(int(m.group(1)))

rows = []
n = 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    n += 1
    try:
        d = yaml.load(open(p, encoding="utf-8"), Loader=L)
    except Exception:
        continue
    if not d:
        continue
    vols = [(v, e) for e in (d.get("editions") or []) for v in (e.get("volumes") or [])]
    if len(vols) != 1:
        continue
    v, e = vols[0]
    num = v.get("number")
    if not num or num < 2:
        continue
    ib = str(v.get("isbn13") or "")
    slug = d.get("slug") or os.path.basename(p)[:-4]
    others = [s for s in iidx.get(ib, []) if s != slug]
    sibs = by_title.get(norm_title(d.get("title")), set()) - {num}
    if others:
        cls = "DUP_ELSEWHERE"
    elif sibs:
        cls = "CACHE_SIBLINGS"
    else:
        cls = "NO_EVIDENCE"
    rows.append((cls, os.path.basename(p)[:-4], str(d.get("title") or "")[:40],
                 "・".join(a.get("name", "") for a in (d.get("authors") or []))[:24],
                 f"v{num}", ib, ",".join(others)[:40] or "-",
                 ",".join(map(str, sorted(sibs)[:10])) or "-"))

rows.sort()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("class\tslug\ttitle\tauthors\tvol\tisbn\tdup_pages\tcache_sibling_vols\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
from collections import Counter
c = Counter(r[0] for r in rows)
print(f"走査{n}頁 → 単巻切り詰め疑い {len(rows)}件: " + " / ".join(f"{k}={v}" for k, v in sorted(c.items())))
print(f"→ {OUT}")
