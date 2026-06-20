#!/usr/bin/env python3
"""
A Phase2 (READ-ONLY): 共有ISBNの「誤claim側」slug各々について、自前の真ISBN(著者×題)が
種1/楽天に在るか探索し、re-point / alias / strip に仕分ける。書込みなし。
入力: shared-isbn-classified.tsv (Phase1) / 出力: data/seeds/shared-isbn-actions.tsv
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

# 1) Phase1分類から「誤claim側」(ALL_WRONG/MIXED/WRONG_plus_unknown) かつ yml存在 を抽出
targets = {}  # slug -> {class, db_authors[], title_core}
for line in (ROOT/'data/seeds/shared-isbn-classified.tsv').open(encoding='utf-8'):
    c = line.rstrip('\n').split('\t')
    if c[0] == 'slug': continue
    sl, cls, ok, wr, un, dba = c[0], c[1], c[2], c[3], c[4], c[5]
    if cls not in ('ALL_WRONG', 'MIXED_deinterleave', 'WRONG_plus_unknown'): continue
    fp = ROOT/'data/manga.v2'/f'{sl}.yml'
    if not fp.exists(): continue  # stale(既にalias/除去済)
    d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    aus = [naz(a.get('name')) for a in (d.get('authors') or []) if a.get('name')]
    aus = [a for a in aus if a]
    targets[sl] = {'class': cls, 'ok': int(ok), 'wrong': int(wr), 'unknown': int(un),
                   'db_authors': aus, 'title_core': naz(d.get('title')),
                   'cur_isbns': set(to13(v.get('isbn13')) for e in d.get('editions', []) for v in e.get('volumes', []) if to13(v.get('isbn13')))}
print(f'誤claim側(yml存在): {len(targets)}', flush=True)

# 2) 種1+楽天を1パスscan。各ISBN(title,authors)で全targetに対し「自前ISBN候補」を集める
#    条件: 著者一致 AND 題core一致(>=2) AND そのISBNが現在のcur_isbns(=誤)でない
own = {sl: [] for sl in targets}
def consider(ib, title, authors_tok):
    if not ib: return
    nt = naz(title)
    if not nt: return
    for sl, t in targets.items():
        if ib in t['cur_isbns']: continue
        tc = t['title_core']
        if not tc or len(tc) < 2 or not (tc in nt or nt in tc): continue
        das = t['db_authors']
        if not das or not authors_tok: continue
        if any((da in ta or ta in da) for da in das for ta in authors_tok):
            own[sl].append((ib, title[:24], '/'.join(authors_tok)[:20]))

g = json.load(open(ROOT/'.cache/madb/metadata101.json', encoding='utf-8'))['@graph']
for r in g:
    ib = to13(first(r.get('schema:isbn')))
    if ib: consider(ib, first(r.get('schema:name')) or '', atok(first(r.get('schema:creator')) or ''))
for line in (ROOT/'.cache/rakuten-isbn.jsonl').open(encoding='utf-8'):
    try: o = json.loads(line); ib = to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
    except: continue
    it = o.get('item') or {}
    if ib: consider(ib, it.get('title', ''), atok(it.get('author', '')))
print('自前ISBN探索 完了', flush=True)

# 3) 仕分け: own>0=RE-POINT候補 / own==0 → 同題のCLEAN_ownerが同著者ならALIAS、別著者ならSTRIP候補
#    CLEAN_ownerの著者照合用: classified から ok>0,wrong==0 を題coreで引けるmap (簡易)
from collections import Counter
action = {}
for sl, t in targets.items():
    o = sorted(set(own[sl]))
    if t['class'] == 'MIXED_deinterleave':
        action[sl] = ('DEINTERLEAVE_review', o)   # 一部正=分割要、機械適用しない
    elif o:
        action[sl] = ('REPOINT', o)               # 自前ISBN有→差替候補
    else:
        action[sl] = ('STRIP_or_ALIAS_review', o)  # 自前無→幻/重複、要個別

cnt = Counter(a for a, _ in action.values())
print('\n=== 仕分け(誤claim側 live) ===')
for k, n in cnt.most_common(): print(f'  {k}: {n}')

out = ROOT/'data/seeds/shared-isbn-actions.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('slug\tclass\taction\twrong\town_isbn_candidates\tdb_authors\town_sample\n')
    for sl in sorted(action, key=lambda s: (action[s][0], -targets[s]['wrong'])):
        act, o = action[sl]
        t = targets[sl]
        smp = '; '.join(f'{ib}({ti}/{au})' for ib, ti, au in o[:3])
        f.write(f"{sl}\t{t['class']}\t{act}\t{t['wrong']}\t{len(o)}\t{'/'.join(t['db_authors'])}\t{smp}\n")
print(f'\n出力: {out}')
