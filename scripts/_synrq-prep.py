# -*- coding: utf-8 -*-
"""短あらすじ requeue(synopsis-short-requeue.tsv)の作業スライスを用意する。

- severe×has_caption=yes のうち、材料(captions)が .cache/enrich-batches/* に在るslugを N 件取り、
  合成材料バッチ .cache/enrich-batches/batch-<SN>.json を書く(丸写し8gramゲートを効かせるため)。
- 同時に digest(現行の短いsynopsis + 全巻caption)を標準出力へ。

usage: python scripts/_synrq-prep.py <SN> [N]     例: python scripts/_synrq-prep.py 9001 45
       CAPLEN=150 で caption 切り詰め長を変更可
その後: data/enrich-out-2026-07/batch-<SN>.json に {slug:{synopsis:...}} を書き
        python scripts/_apply-enrich-batch.py <SN> --requeue [--apply]
        python scripts/_synrqdone.py <SN>
"""
import json, os, sys, glob, html, re, io
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'docs', 'production-diagnostics', 'synopsis-short-requeue.tsv')
BATCHDIR = os.path.join(ROOT, '.cache', 'enrich-batches')
CAP = int(os.environ.get('CAPLEN', '200'))

SN = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 45

rows = [l.rstrip('\n').split('\t') for l in io.open(TSV, encoding='utf-8')]
h = rows[0]
iT, iC, iA, iS, iTi, iCur = (h.index(x) for x in ('tier', 'has_caption', 'anilist_id', 'slug', 'title', 'current_synopsis'))
targets = [r for r in rows[1:] if len(r) >= len(h) and r[iT] == 'severe' and r[iC] == 'yes']
want = {r[iS]: r for r in targets}

mat = {}
for p in sorted(glob.glob(os.path.join(BATCHDIR, 'batch-*.json'))):
    if os.path.basename(p) == f'batch-{SN}.json':
        continue
    try:
        d = json.load(io.open(p, encoding='utf-8'))
    except Exception:
        continue
    for it in (d['items'] if isinstance(d, dict) else d):
        s = it.get('slug')
        if s in want and s not in mat and (it.get('captions') or []):
            mat[s] = it

picked = [mat[s] for s in want if s in mat][:N]
json.dump({'kind': 'full', 'items': picked},
          io.open(os.path.join(BATCHDIR, f'batch-{SN}.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)

for it in picked:
    r = want[it['slug']]
    print(f'--- {it["slug"]} | {r[iTi]} | {"/".join(it.get("authors") or [])} | {it.get("n_vols")}巻 | aid={r[iA]}')
    print(f'  [旧syn{len(r[iCur])}字] {r[iCur]}')
    for c in (it.get('captions') or []):
        cap = re.sub(r'\s+', ' ', html.unescape(c.get('caption') or '')).strip()[:CAP]
        print(f'  [v{c.get("vol")}] {cap}')

print(f'### 出力 {len(picked)}件 / severe×caption有 残 {len(targets)}件 (材料在庫 {len(mat)}件)', file=sys.stderr)
