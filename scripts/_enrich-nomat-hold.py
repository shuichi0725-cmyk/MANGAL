# -*- coding: utf-8 -*-
"""harvest したのに楽天 caption が取れなかった slug を hold 台帳へ退避する。

★これをやらないと、caption 無しの頁は done にも hold にも入らないため
  `_enrich-newest-scan.py` のバックログ先頭に永久に居座り、毎周 live 照会だけを浪費する
  (2026-08-06 実踏: 115頁harvest → 材料9件、残りは全部この再照会分だった)。

usage: python scripts/_enrich-nomat-hold.py
  読む: .cache/enrich-slice-slugs.txt (直近スライス) + .cache/enrich/materials.jsonl
  書く: docs/production-diagnostics/enrich-hold.tsv へ追記
"""
import io, json, os, sys, datetime
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

slice_slugs = [s for s in io.open(os.path.join(ROOT, '.cache', 'enrich-slice-slugs.txt'), encoding='utf-8').read().split(',') if s]
have, title = set(), {}
for line in io.open(os.path.join(ROOT, '.cache', 'enrich', 'materials.jsonl'), encoding='utf-8'):
    d = json.loads(line)
    title[d['slug']] = d.get('title', '')
    if [c for c in (d.get('captions') or []) if (c.get('caption') or '').strip()]:
        have.add(d['slug'])

hp = os.path.join(ROOT, 'docs', 'production-diagnostics', 'enrich-hold.tsv')
held = set()
for i, l in enumerate(io.open(hp, encoding='utf-8')):
    if i:
        held.add(l.split('\t')[0])

at = datetime.date.today().isoformat()
new = [s for s in slice_slugs if s not in have and s not in held]
with io.open(hp, 'a', encoding='utf-8', newline='') as f:
    for s in new:
        f.write('\t'.join([s, title.get(s, ''), at, 'nomat', '楽天にcaptionなし(harvest済)']) + '\n')
print('hold追加 %d件 / スライス%d / 材料あり%d' % (len(new), len(slice_slugs), len(have)))
