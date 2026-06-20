#!/usr/bin/env python3
"""
奇子型(同一著者の版違い混在)検出 (READ-ONLY): cm104(metadata104)で多版の作品を把握し、
本番standard editionが「ISBN出版者記号の混在(=別版の巻が紛れ)」+「発売年の飛び」を示すページを候補化。
出力: data/seeds/ayako-candidates.tsv
"""
import sys, json, re, unicodedata, yaml
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent

def first(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str): return x
            if isinstance(x, dict) and x.get('@value'): return x['@value']
    return v if isinstance(v, str) else (v.get('@value','') if isinstance(v,dict) else '')
def naz(s): return re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-/／∥]', '', unicodedata.normalize('NFKC', str(s or ''))).lower()
def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''
def pubgrp(ib):  # ISBN 出版者記号の粗いグループ(9784 + 次3桁)
    return ib[4:7] if len(ib) == 13 else ''

# 1) cm104 多版作品 (name+creator → editions)
print('cm104ロード...', flush=True)
g = json.load(open(ROOT/'.cache/madb/metadata104.json', encoding='utf-8'))
graph = g.get('@graph', g)
multied = defaultdict(list)
for r in graph:
    if first(r.get('schema:genre')) != 'マンガ単行本シリーズ': continue
    nm = first(r.get('schema:name')); cr = re.sub(r'\[[^\]]*\]', '', first(r.get('schema:creator')))
    if not nm: continue
    key = (naz(nm), naz(cr))
    multied[key].append({'brand': first(r.get('schema:brand')), 'vols': first(r.get('schema:numberOfItems')),
                          'pub': first(r.get('schema:publisher')).split('　∥')[0], 'year': str(first(r.get('schema:datePublished')))[:4]})
multi = {k: v for k, v in multied.items() if len({(e['brand'], e['pub']) for e in v}) >= 2}
print(f'  cm104多版作品 {len(multi)}', flush=True)

# 2) manga.v2 standard で 版混在シグナル
print('manga.v2走査...', flush=True)
cands = []
n = 0
for fp in (ROOT/'data/manga.v2').glob('*.yml'):
    try: d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    except: continue
    if not isinstance(d, dict): continue
    n += 1
    au = naz('/'.join(a.get('name','') for a in (d.get('authors') or [])))
    tnaz = naz(d.get('title'))
    for e in (d.get('editions') or []):
        if e.get('type') != 'standard': continue
        vols = e.get('volumes') or []
        grps = set(); years = []
        for v in vols:
            ib = to13(v.get('isbn13'))
            if ib: grps.add(pubgrp(ib))
            yr = str(v.get('release_date') or '')[:4]
            if yr.isdigit(): years.append(int(yr))
        if len(grps) >= 2 and years and (max(years)-min(years)) >= 5:
            # cm104多版に該当するか(著者一致 or 題一致)
            cm = None
            for (cnm, ccr), eds in multi.items():
                if tnaz and (tnaz == cnm or tnaz in cnm or cnm in tnaz) and au and ccr and (au in ccr or ccr in au):
                    cm = eds; break
            cands.append({'slug': d.get('slug'), 'title': d.get('title'), 'au': [a.get('name') for a in (d.get('authors') or [])],
                          'nvol': len(vols), 'pubgrps': sorted(grps), 'yearspan': f'{min(years)}-{max(years)}',
                          'cm104': len(cm) if cm else 0})
print(f'  走査{n} / 候補{len(cands)}', flush=True)

cands.sort(key=lambda c: (-c['cm104'], -len(c['pubgrps'])))
out = ROOT/'data/seeds/ayako-candidates.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('slug\ttitle\tauthors\tnvol\tpubgrps\tyearspan\tcm104_editions\n')
    for c in cands:
        f.write(f"{c['slug']}\t{c['title']}\t{'/'.join(c['au'])}\t{c['nvol']}\t{','.join(c['pubgrps'])}\t{c['yearspan']}\t{c['cm104']}\n")
withcm = sum(1 for c in cands if c['cm104'] >= 2)
print(f'出力: {out}\n  全候補{len(cands)} / うちcm104多版裏付けあり {withcm}')
