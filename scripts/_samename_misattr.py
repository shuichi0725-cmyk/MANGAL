#!/usr/bin/env python3
"""
同名群の誤帰属/stray検出 (READ-ONLY): samename-groups の全ページについて、
現ISBNの真著者(種1/楽天) vs ページ著者ラベル を照合。食い違う=誤帰属/汚染候補。
出力: data/seeds/samename-misattr.tsv
"""
import sys, json, re, unicodedata, yaml
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent

def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''
def first(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str): return x
            if isinstance(x, dict) and x.get('@value'): return x['@value']
    return v if isinstance(v, str) else ''
VAR = str.maketrans('髙﨑德濵齋齊澤眞嶋', '高崎徳浜斎斉沢真島')
def nm(s): return re.sub(r'[\s　・,，、。\-/／･\.]', '', unicodedata.normalize('NFKC', str(s or '')).translate(VAR)).lower()
def atok(creator):
    s = re.sub(r'\[[^\]]*\]', '', str(creator or ''))
    return [nm(p) for p in re.split(r'[、,/／;；]| ∥ |∥', s) if nm(p)]

# 1) 同名群の全slug + そのISBN/著者ラベル
done = set(yaml.safe_load((ROOT/'data/seeds/dup-merge-alias.yml').read_text(encoding='utf-8')) or {})
slugs = set()
for line in (ROOT/'data/seeds/samename-groups.tsv').open(encoding='utf-8'):
    c = line.rstrip('\n').split('\t')
    if c[0] not in ('SAME_AUTHOR', 'DIFF_AUTHOR'): continue
    for s in c[2].split(','):
        if s not in done: slugs.add(s)
pages = {}
allisbn = set()
for s in slugs:
    fp = ROOT/'data/manga.v2'/f'{s}.yml'
    if not fp.exists(): continue
    d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    ibs = [to13(v.get('isbn13')) for e in (d.get('editions') or []) for v in (e.get('volumes') or []) if to13(v.get('isbn13'))]
    if not ibs: continue
    pages[s] = {'label': [nm(a.get('name')) for a in (d.get('authors') or []) if a.get('name')],
                'label_disp': [a.get('name') for a in (d.get('authors') or [])], 'title': d.get('title'), 'ibs': ibs}
    allisbn |= set(ibs)
print(f'同名群 live page {len(pages)} / ISBN {len(allisbn)}', flush=True)

# 2) 種1+楽天 → ISBN真著者(該当分のみ)
TRUE = {}
g = json.load(open(ROOT/'.cache/madb/metadata101.json', encoding='utf-8'))['@graph']
for r in g:
    ib = to13(first(r.get('schema:isbn')))
    if ib in allisbn: TRUE[ib] = atok(first(r.get('schema:creator')))
for line in (ROOT/'.cache/rakuten-isbn.jsonl').open(encoding='utf-8'):
    try: o = json.loads(line); ib = to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
    except: continue
    if ib in allisbn and ib not in TRUE:
        TRUE[ib] = atok((o.get('item') or {}).get('author', ''))
print(f'真著者判明ISBN {len(TRUE)}/{len(allisbn)}', flush=True)

def match(label, tru):
    if not label or not tru: return None
    return any((l in t or t in l) for l in label for t in tru)

# 3) ページ単位: 現ISBNの真著者がラベルと食い違うか
rows = []
for s, p in pages.items():
    ok = wrong = unk = 0
    wlist = []
    for ib in p['ibs']:
        t = TRUE.get(ib)
        if not t: unk += 1; continue
        m = match(p['label'], t)
        if m: ok += 1
        else: wrong += 1; wlist.append((ib, '/'.join(t)[:18]))
    # ラベルと一致ゼロ かつ 誤>=1 = 誤帰属候補
    if ok == 0 and wrong >= 1:
        rows.append((wrong, s, '/'.join(p['label_disp']), p['title'], wlist[:3]))
rows.sort(key=lambda r: -r[0])
out = ROOT/'data/seeds/samename-misattr.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('wrong_n\tslug\tlabel_author\ttitle\twrong_isbn_trueauthor\n')
    for w, s, lab, t, wl in rows:
        f.write(f"{w}\t{s}\t{lab}\t{t}\t{'; '.join(f'{ib}({a})' for ib,a in wl)}\n")
print(f'誤帰属候補(ラベル一致0+誤>=1): {len(rows)} → {out}')
