# -*- coding: utf-8 -*-
"""_enrichgap-prep.py で切ったスライスの slug を消し込む(= .cache/enrichgap-done.txt へ追記)。

usage: python scripts/_enrichgap-done.py <SN>
材料batch(.cache/enrich-batches/batch-<SN>.json)の slug を done に足す。
"""
import json, io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SN = sys.argv[1]
b = json.load(io.open(os.path.join(ROOT, '.cache', 'enrich-batches', 'batch-%s.json' % SN), encoding='utf-8'))
slugs = [it['slug'] for it in b.get('items') or []]

dp = os.path.join(ROOT, '.cache', 'enrichgap-done.txt')
done = set()
if os.path.exists(dp):
    done = {x.strip() for x in io.open(dp, encoding='utf-8') if x.strip()}
new = [s for s in slugs if s not in done]
with io.open(dp, 'a', encoding='utf-8') as f:
    for s in new:
        f.write(s + '\n')
sys.stdout.reconfigure(encoding='utf-8')
print('done+%d (batch slugs=%d) / done累計 %d' % (len(new), len(slugs), len(done) + len(new)))
