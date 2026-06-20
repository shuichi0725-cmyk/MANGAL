#!/usr/bin/env python3
"""
統合台帳 operations.jsonl 生成 (= 散在する18個の *-changelog.jsonl を1本に集約)。
各cleanup/intake操作を {op_source, slug, related, at, raw} の正規行に束ねる。READ-ONLY(集約のみ)。
設計: docs/intake-manifest-gate-design.md §6 (=台帳=記憶)。
出力: data/seeds/intake-manifest/operations.jsonl (at昇順)
"""
import sys, json, glob, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT/'data/seeds'
OUTDIR = ROOT/'data/seeds/intake-manifest'; OUTDIR.mkdir(parents=True, exist_ok=True)

SLUG_KEYS = ['slug', 'dropped', 'dup', 'target', 'deint', 'dedup', 'restore', 'repoint',
             'repoint4', 'sharedisbn_repoint', 'strip_needs_content', 'deint_empty_needs_content',
             'alias_needscontent', 'removed_slug']
REL_KEYS = ['canon', 'canonical', 'owner', 'related']
TS_KEYS = ['at', 'applied_at', 'ts', 'detected_at']

def src_name(fn):
    b = Path(fn).name
    b = re.sub(r'\.jsonl$', '', b)
    b = re.sub(r'-?changelog$|^_', '', b)
    return b or 'change-log'

def pick(o, keys):
    for k in keys:
        if k in o and o[k]:
            v = o[k]
            return v[0] if isinstance(v, list) and v else (v if not isinstance(v, list) else None)
    return None

rows = []
files = sorted(glob.glob(str(SEEDS/'*changelog*.jsonl'))) + [str(SEEDS/'_change-log.jsonl')]
files = sorted(set(f for f in files if Path(f).exists()))
for f in files:
    src = src_name(f)
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: o = json.loads(line)
        except: continue
        rows.append({'op_source': src, 'slug': pick(o, SLUG_KEYS),
                     'related': pick(o, REL_KEYS), 'at': pick(o, TS_KEYS) or '', 'raw': o})

rows.sort(key=lambda r: (str(r['at']), r['op_source']))
out = OUTDIR/'operations.jsonl'
with open(out, 'w', encoding='utf-8') as w:
    for r in rows:
        w.write(json.dumps(r, ensure_ascii=False)+'\n')

from collections import Counter
bysrc = Counter(r['op_source'] for r in rows)
print(f'集約 {len(rows)}操作 / {len(files)}台帳 → {out}')
for s, n in bysrc.most_common(): print(f'  {s}: {n}')
print('slug抽出率:', sum(1 for r in rows if r['slug']), '/', len(rows))
