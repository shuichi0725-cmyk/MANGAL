#!/usr/bin/env python3
"""
同名スラッグ群の検出 (READ-ONLY): 正規化タイトルが同じ複数slugを群化。
同題+同著者(=重複の疑い濃)を最優先で出す。直さず確認用。
出力: data/seeds/samename-groups.tsv
"""
import sys, re, unicodedata, yaml, json
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent

def hk(s): return re.sub(r'[ぁ-ん]', lambda m: chr(ord(m.group())+0x60), s)
def naz(s): return hk(re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-/／∥0-9０-９a-z]', '', unicodedata.normalize('NFKC', str(s or '')).lower()))
def nau(s):
    VAR = str.maketrans('髙﨑德濵齋齊澤眞嶋', '高崎徳浜斎斉沢真島')
    return re.sub(r'[\s　・]', '', unicodedata.normalize('NFKC', str(s or '')).translate(VAR))
def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''

print('LIVE走査...', flush=True)
bytitle = defaultdict(list)
n = 0
for fp in (ROOT/'data/manga.v2').glob('*.yml'):
    try: d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    except: continue
    if not isinstance(d, dict): continue
    n += 1
    t = naz(d.get('title'))
    if not t or len(t) < 2: continue
    aus = frozenset(nau(a.get('name')) for a in (d.get('authors') or []) if a.get('name'))
    ibs = frozenset(to13(v.get('isbn13')) for e in (d.get('editions') or []) for v in (e.get('volumes') or []) if to13(v.get('isbn13')))
    bytitle[t].append({'slug': d.get('slug'), 'title': d.get('title'),
                       'au': [a.get('name') for a in (d.get('authors') or [])], 'nau': aus,
                       'nvol': sum(len(e.get('volumes', [])) for e in (d.get('editions') or [])), 'ibs': ibs})
print(f'  {n}ページ', flush=True)

groups = {t: v for t, v in bytitle.items() if len(v) >= 2}
# 各群を分類: SAME_AUTHOR(同題+著者重なり=重複疑) / DIFF_AUTHOR(別作の可能性=正当多) / UNKNOWN_AU
rows = []
for t, members in groups.items():
    # 著者重なりペアがあるか
    sus = False
    for i in range(len(members)):
        for j in range(i+1, len(members)):
            a, b = members[i]['nau'], members[j]['nau']
            if a and b and (a & b): sus = True
    cls = 'SAME_AUTHOR' if sus else ('UNKNOWN_AU' if any(not m['nau'] for m in members) else 'DIFF_AUTHOR')
    rows.append((cls, len(members), members))

out = ROOT/'data/seeds/samename-groups.tsv'
order = {'SAME_AUTHOR': 0, 'UNKNOWN_AU': 1, 'DIFF_AUTHOR': 2}
with open(out, 'w', encoding='utf-8') as f:
    f.write('class\tn\tslugs\tauthors\tnvols\tisbn_overlap\n')
    for cls, nmem, members in sorted(rows, key=lambda r: (order[r[0]], -r[1])):
        slugs = ','.join(m['slug'] for m in members)
        aus = ' || '.join('/'.join(m['au']) for m in members)
        nv = ','.join(str(m['nvol']) for m in members)
        # ISBN重複の有無(同題群内)
        allib = [m['ibs'] for m in members]
        ov = 'yes' if any(allib[i] & allib[j] for i in range(len(allib)) for j in range(i+1, len(allib))) else 'no'
        f.write(f"{cls}\t{nmem}\t{slugs}\t{aus}\t{nv}\t{ov}\n")
from collections import Counter
c = Counter(r[0] for r in rows)
print('同名群:', dict(c), '/ 総群', len(rows))
print(f'出力: {out}')
