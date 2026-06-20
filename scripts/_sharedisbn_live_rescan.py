#!/usr/bin/env python3
"""
A 再スキャン (LIVE): resolve-master.tsv は古snapshot(t3-fix/torichigae等の後発修正を含まない)。
本番 data/manga.v2 の現ISBNから「今なお複数slugが共有するISBN」を直接抽出し、真owner判定で再分類。READ-ONLY。
出力: data/seeds/shared-isbn-live.tsv (slug別) + .cache/_sharedisbn_live.json
"""
import sys, json, re, unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml

def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''
def first(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str): return x
            if isinstance(x, dict) and x.get('@value'): return x['@value']
    return v
def hk(s): return re.sub(r'[ぁ-ん]', lambda m: chr(ord(m.group())+0x60), s)
def naz(s): return hk(re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-/／∥0-9０-９]', '', unicodedata.normalize('NFKC', str(s or '')))).lower()
def atok(creator):
    s = re.sub(r'\[[^\]]*\]', '', str(creator or ''))
    return [naz(p) for p in re.split(r'[、,/／;；]| ∥ |∥', s) if naz(p)]

print('LIVE data/manga.v2 走査...', flush=True)
SRC = ROOT/'data/manga.v2'
isbn2slugs = {}   # isbn -> set(slug)
slug_isbns = {}   # slug -> set(isbn)
slug_auth = {}    # slug -> [naz authors]
slug_title = {}
n = 0
for fp in SRC.glob('*.yml'):
    try: d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    except: continue
    if not isinstance(d, dict): continue
    sl = d.get('slug') or fp.stem
    ibs = set()
    for e in (d.get('editions') or []):
        for v in (e.get('volumes') or []):
            ib = to13(v.get('isbn13'))
            if ib: ibs.add(ib)
    if not ibs: continue
    slug_isbns[sl] = ibs
    au = [naz(a.get('name')) for a in (d.get('authors') or []) if a.get('name')]
    au += [naz(a.get('name')) for a in (d.get('original_authors') or []) if a.get('name')]
    slug_auth[sl] = [a for a in au if a]
    slug_title[sl] = naz(d.get('title'))
    for ib in ibs: isbn2slugs.setdefault(ib, set()).add(sl)
    n += 1
    if n % 10000 == 0: print(f'  {n}...', flush=True)
print(f'  {n}ページ走査完了', flush=True)

# 現在なお共有(>=2 slug)のISBN
shared = {ib: sl for ib, sl in isbn2slugs.items() if len(sl) >= 2}
shared_slugs = sorted({s for ss in shared.values() for s in ss})
print(f'★現在なお共有ISBN: {len(shared)} / 関与slug: {len(shared_slugs)}', flush=True)

# 真owner判定: 種1/楽天で共有ISBNの真(著者tokens)を引く
SH = set(shared)
TRUE = {}
g = json.load(open(ROOT/'.cache/madb/metadata101.json', encoding='utf-8'))['@graph']
for r in g:
    ib = to13(first(r.get('schema:isbn')))
    if ib in SH: TRUE[ib] = {'title': first(r.get('schema:name')) or '', 'au': atok(first(r.get('schema:creator')) or ''), 'src': '種1'}
for line in (ROOT/'.cache/rakuten-isbn.jsonl').open(encoding='utf-8'):
    try: o = json.loads(line); ib = to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
    except: continue
    if ib in SH and ib not in TRUE:
        it = o.get('item') or {}; TRUE[ib] = {'title': it.get('title', ''), 'au': atok(it.get('author', '')), 'src': '楽天'}

def amatch(das, tas):
    if not das or not tas: return None
    return any((d in t or t in d) for d in das for t in tas)

# slug別 判定
per = {}
for ib, slset in shared.items():
    t = TRUE.get(ib)
    for sl in slset:
        p = per.setdefault(sl, {'ok': 0, 'wrong': 0, 'unknown': 0, 'wrong_isbns': []})
        if not t: p['unknown'] += 1; continue
        m = amatch(slug_auth.get(sl), t['au'])
        if m is True: p['ok'] += 1
        elif m is False:
            p['wrong'] += 1; p['wrong_isbns'].append((ib, t['title'][:24], '/'.join(t['au'])[:18], len(slset)))
        else: p['unknown'] += 1

def cls(p):
    if p['wrong'] == 0 and p['ok'] > 0: return 'CLEAN_owner'
    if p['wrong'] > 0 and p['ok'] == 0 and p['unknown'] == 0: return 'ALL_WRONG'
    if p['wrong'] > 0 and p['ok'] > 0: return 'MIXED'
    if p['wrong'] > 0: return 'WRONG+unknown'
    return 'UNKNOWN_only'
from collections import Counter
summ = Counter(cls(p) for p in per.values())
print('\n=== LIVE slug分類 ===')
for k, v in summ.most_common(): print(f'  {k}: {v}')

out = ROOT/'data/seeds/shared-isbn-live.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('slug\tclass\tok\twrong\tunknown\tdb_authors\twrong_isbn_sample\ttrue_owner_sample\tmax_nshare\n')
    for sl in sorted(per, key=lambda s: (cls(per[s]), -per[s]['wrong'])):
        p = per[sl]
        w = p['wrong_isbns'][0] if p['wrong_isbns'] else ('', '', '', 0)
        mx = max([x[3] for x in p['wrong_isbns']], default=(max((len(shared[ib]) for ib in slug_isbns.get(sl, []) if ib in shared), default=0)))
        f.write(f"{sl}\t{cls(p)}\t{p['ok']}\t{p['wrong']}\t{p['unknown']}\t{'/'.join(slug_auth.get(sl) or [])}\t{w[0]}\t{w[1]}/{w[2]}\t{mx}\n")
json.dump({'summary': dict(summ), 'shared_isbn_now': len(shared), 'slugs_involved': len(shared_slugs)},
          open(ROOT/'.cache/_sharedisbn_live.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'\n出力: {out}')
