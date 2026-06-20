#!/usr/bin/env python3
"""
A 母集団 reconcile (台帳+実DB, READ-ONLY): shared-isbn-actions.tsv の全候補(誤claim側)の
★現在の yml★ を読み、各現ISBNの真著者を種1/楽天で照合。今なお誤著者の巻を抱える物だけ抽出し
安全度で仕分け。stale resolve-masterに依存しない。
出力: data/seeds/shared-isbn-reconcile.tsv
仕分け:
 SAFE_STRIP   = 単一edition・null無・本人巻≥1・誤巻≥1 → 誤巻除去で確定(段1と同型、自動候補)
 REPOINT_full = 本人巻0・誤巻のみ → 自前ISBNへ要差替(個別)
 REVIEW       = null巻有/複数edition/unknown有 → 人手(reset型の罠)
 CLEAN_NOW    = 誤巻0 → 既に解決(skip)
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

# 1) 候補slug(全wrong-claimant)
cands = []
for line in (ROOT/'data/seeds/shared-isbn-actions.tsv').open(encoding='utf-8'):
    c = line.rstrip('\n').split('\t')
    if c[0] == 'slug' or len(c) < 3: continue
    cands.append(c[0])
cands = sorted(set(cands))

# 2) 各候補の現yml読み
info = {}
allisbn = set()
for sl in cands:
    fp = ROOT/'data/manga.v2'/f'{sl}.yml'
    if not fp.exists(): continue
    d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    aus = [naz(a.get('name')) for a in (d.get('authors') or []) if a.get('name')]
    aus = [a for a in aus if a]
    vols = []
    for e in (d.get('editions') or []):
        for v in (e.get('volumes') or []):
            ib = to13(v.get('isbn13'))
            vols.append({'isbn': ib, 'raw_isbn': v.get('isbn13')})
            if ib: allisbn.add(ib)
    info[sl] = {'authors': aus, 'title': d.get('title'), 'n_edition': len(d.get('editions') or []),
                'vols': vols, 'has_null': any(not x['isbn'] for x in vols),
                'authors_disp': [a.get('name') for a in (d.get('authors') or [])]}
print(f'候補(yml存在) {len(info)} / 現ISBN {len(allisbn)}', flush=True)

# 3) 現ISBNの真著者(種1優先, 楽天補完) — 候補ISBN分のみ
TRUE = {}
g = json.load(open(ROOT/'.cache/madb/metadata101.json', encoding='utf-8'))['@graph']
for r in g:
    ib = to13(first(r.get('schema:isbn')))
    if ib in allisbn: TRUE[ib] = {'au': atok(first(r.get('schema:creator')) or ''), 't': first(r.get('schema:name')) or ''}
for line in (ROOT/'.cache/rakuten-isbn.jsonl').open(encoding='utf-8'):
    try: o = json.loads(line); ib = to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
    except: continue
    if ib in allisbn and ib not in TRUE:
        it = o.get('item') or {}; TRUE[ib] = {'au': atok(it.get('author', '')), 't': it.get('title', '')}
print(f'真著者判明ISBN {len(TRUE)}/{len(allisbn)}', flush=True)

def amatch(das, tas):
    if not das or not tas: return None
    return any((d in t or t in d) for d in das for t in tas)

# 4) 仕分け
rows = []
for sl, m in info.items():
    own = wrong = unk = 0
    wrong_isbns = []
    for v in m['vols']:
        ib = v['isbn']
        if not ib: continue
        t = TRUE.get(ib)
        r = amatch(m['authors'], t['au']) if t else None
        if r is True: own += 1
        elif r is False: wrong += 1; wrong_isbns.append((ib, t['t'][:20], '/'.join(t['au'])[:16]))
        else: unk += 1
    if wrong == 0:
        verdict = 'CLEAN_NOW'
    elif m['has_null'] or m['n_edition'] > 1 or unk > 0:
        verdict = 'REVIEW'
    elif own >= 1:
        verdict = 'SAFE_STRIP'
    else:
        verdict = 'REPOINT_full'
    rows.append({'slug': sl, 'verdict': verdict, 'own': own, 'wrong': wrong, 'unk': unk,
                 'n_ed': m['n_edition'], 'null': m['has_null'], 'authors': '/'.join(m['authors_disp']),
                 'wrong_isbns': wrong_isbns})

from collections import Counter
summ = Counter(r['verdict'] for r in rows)
print('\n=== reconcile 仕分け(現状) ===')
for k, n in summ.most_common(): print(f'  {k}: {n}')

out = ROOT/'data/seeds/shared-isbn-reconcile.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('slug\tverdict\town\twrong\tunk\tn_ed\tnull\tauthors\twrong_isbns\n')
    for r in sorted(rows, key=lambda x: (x['verdict'], -x['wrong'])):
        wi = '; '.join(f'{ib}({t}/{a})' for ib, t, a in r['wrong_isbns'][:3])
        f.write(f"{r['slug']}\t{r['verdict']}\t{r['own']}\t{r['wrong']}\t{r['unk']}\t{r['n_ed']}\t{r['null']}\t{r['authors']}\t{wi}\n")
# SAFE_STRIP の除去ISBN map を json で(apply用)
strip_map = {r['slug']: sorted(set(ib for ib, _, _ in r['wrong_isbns'])) for r in rows if r['verdict'] == 'SAFE_STRIP'}
json.dump(strip_map, open(ROOT/'.cache/_safe_strip_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'\n出力: {out}')
print(f'  SAFE_STRIP {len(strip_map)}件 → .cache/_safe_strip_map.json')
