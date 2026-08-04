# -*- coding: utf-8 -*-
"""【巻抜け残 × 楽天live】ローカル種に無い欠番巻を楽天Books liveで収穫(生itemを逐次保存)。

★照会は必ず _lookup.py の rakuten_live_retry 経由(endpoint/header/レート/backoffの正はあちら)。
 - 対象 = vol_gap_virtual_remain.tsv の頁のうち、実際に欠番がある物
 - ①頁題で1回(hits=30) → 足りない欠番だけ ②「題 N」で追い打ち
 - グローバルレートゲート1.3秒/req・429はbackoff吸収・逐次flush・done-setで再開可能
 - 判定はしない(収穫のみ)。ゲートは _volgap-live-match.py 側。

使用: python scripts/_volgap-live-harvest.py [--limit N]
"""
import os, sys, json, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _lookup as L
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, ".cache", "volgap-live-rakuten.jsonl")
REM = os.path.join(ROOT, "docs", "production-diagnostics", "vol_gap_virtual_remain.tsv")
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

env = dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".env.local"), encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
s2s = json.load(open(os.path.join(ROOT, ".cache", "slug2stem.json"), encoding="utf-8"))

done = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        try:
            done.add(json.loads(line)["stem"])
        except Exception:
            pass

targets = []
for line in list(open(REM, encoding="utf-8"))[1:]:
    slug = line.split("\t")[0]
    stem = slug if os.path.exists(os.path.join(SRC, slug + ".yml")) else s2s.get(slug)
    if not stem or stem in done:
        continue
    d = yaml.safe_load(open(os.path.join(SRC, stem + ".yml"), encoding="utf-8")) or {}
    miss = set()
    for e in (d.get("editions") or []):
        ns = sorted({int(v["number"]) for v in (e.get("volumes") or []) if v.get("number")})
        if len(ns) >= 2:
            miss |= {n for n in range(ns[0], ns[-1] + 1) if n not in ns}
    if miss and d.get("title"):
        targets.append((stem, d["title"], sorted(miss)))
if LIMIT:
    targets = targets[:LIMIT]
n_slot = sum(len(m) for _, _, m in targets)
print(f"対象 {len(targets)} 頁 / 欠番 {n_slot} 巻 (済 {len(done)})", flush=True)


def vols_in(items):
    got = {}
    for it in items:
        raw = R.clean_title(it.get("title", ""))
        v, _res = R.parse_vol(raw)
        if v is not None:
            got.setdefault(v, 0)
            got[v] += 1
    return got


fh = open(OUT, "a", encoding="utf-8")
n_item = 0
for i, (stem, title, miss) in enumerate(targets, 1):
    items = []
    try:
        items = L.rakuten_live_retry(env, title=title, hits=30) or []
    except Exception as e:
        print(f"  skip {stem}: {type(e).__name__}", flush=True)
    got = vols_in(items)
    for n in miss:
        if n in got:
            continue
        try:
            extra = L.rakuten_live_retry(env, title=f"{title} {n}", hits=30) or []
            items += extra
        except Exception as e:
            print(f"  skip {stem} v{n}: {type(e).__name__}", flush=True)
            break
    fh.write(json.dumps({"stem": stem, "title": title, "missing": miss, "items": items}, ensure_ascii=False) + "\n")
    fh.flush()
    n_item += len(items)
    if i % 20 == 0:
        print(f"  {i}/{len(targets)} 頁 / item {n_item:,}", flush=True)
fh.close()
print(f"完了 {len(targets)} 頁 / item {n_item:,} → {OUT}", flush=True)
