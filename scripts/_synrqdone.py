# -*- coding: utf-8 -*-
"""短あらすじ requeue の消し込み。合成バッチに入っていたslugを synopsis-short-requeue.tsv から除去。

usage: python scripts/_synrqdone.py <SN> [...]
"""
import json, os, sys, io
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'docs', 'production-diagnostics', 'synopsis-short-requeue.tsv')
OUTDIR = os.path.join(ROOT, 'data', 'enrich-out-2026-07')

done = set()
for n in sys.argv[1:]:
    d = json.load(io.open(os.path.join(OUTDIR, f'batch-{n}.json'), encoding='utf-8'))
    done |= set(d.keys())

lines = io.open(TSV, encoding='utf-8').read().split('\n')
head, body = lines[0], [l for l in lines[1:] if l.strip()]
kept = [l for l in body if l.split('\t')[4] not in done]
io.open(TSV, 'w', encoding='utf-8').write('\n'.join([head] + kept) + '\n')

sev_yes = sum(1 for l in kept if l.split('\t')[0] == 'severe' and l.split('\t')[2] == 'yes')
print(f'removed={len(body)-len(kept)} (batch slugs={len(done)}) / remaining={len(kept)} (severe×caption有 {sev_yes})')
print(','.join(sorted(done)))
