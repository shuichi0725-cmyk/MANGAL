# -*- coding: utf-8 -*-
"""キャッチ/詳細が空の頁(=skill enrich-catch-synopsis 優先①)の作業スライスを切る。

入力 = .cache/enrich/materials.jsonl (= _enrich-captions.py --missing の出力)
出力 = .cache/enrich-batches/batch-<SN>.json (8gram丸写しゲート用の材料) + 標準出力に digest

usage: MINVOL=2 python scripts/_enrichgap-prep.py <SN> <N> [> digest.txt]
  MINVOL=2 (既定) = 2巻以上 → キャッチ+詳細+ジャンルのフル対象
  MINVOL=1 かつ MAXVOL=1 → 1巻のみ = ジャンルのみ対象
処理済みの消し込みは _enrichgap-done.py が担う(.cache/enrichgap-done.txt に追記)。
"""
import json, io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SN = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 40
MINVOL = int(os.environ.get('MINVOL', '2'))
MAXVOL = int(os.environ.get('MAXVOL', '9999'))
CAPLEN = int(os.environ.get('CAPLEN', '95'))

done = set()
dp = os.path.join(ROOT, '.cache', 'enrichgap-done.txt')
if os.path.exists(dp):
    done = {x.strip() for x in io.open(dp, encoding='utf-8') if x.strip()}

picked = []
for line in io.open(os.path.join(ROOT, '.cache', 'enrich', 'materials.jsonl'), encoding='utf-8'):
    d = json.loads(line)
    if d['slug'] in done:
        continue
    caps = d.get('captions') or []
    nv = d.get('n_vols') or 0
    if not caps or not (MINVOL <= nv <= MAXVOL):
        continue
    picked.append(d)
    if len(picked) >= N:
        break

os.makedirs(os.path.join(ROOT, '.cache', 'enrich-batches'), exist_ok=True)
with io.open(os.path.join(ROOT, '.cache', 'enrich-batches', 'batch-%s.json' % SN), 'w', encoding='utf-8') as f:
    json.dump({'kind': 'full', 'items': picked}, f, ensure_ascii=False)

out = []
for d in picked:
    out.append('--- %s | %s | %s | %s巻 | catch=%s syn=%s genre=%s' % (
        d['slug'], d.get('title', ''), '/'.join(d.get('authors') or []), d.get('n_vols'),
        '有' if d.get('has_catch') else '空',
        '有' if d.get('has_synopsis') else '空',
        ','.join(d.get('genres_now') or []) or '空'))
    for c in (d.get('captions') or [])[:3]:
        out.append('  [v%s] %s' % (c.get('vol'), (c.get('caption') or '')[:CAPLEN]))
sys.stdout.reconfigure(encoding='utf-8')
print('\n'.join(out))
print('### 出力 %d件 / MINVOL=%d MAXVOL=%d / done累計 %d' % (len(picked), MINVOL, MAXVOL, len(done)))
