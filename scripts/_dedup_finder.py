#!/usr/bin/env python3
"""
重複ページ検出 (READ-ONLY): 同一作品が二重に存在するページを「ISBN集合の一致/高重複」で検出。
data/manga.v2 を一回走査→ slug→(isbns,author,title)。 同ISBN集合 or 高Jaccard の slug群を候補化。
既alias(dup-merge-alias.yml + operations.jsonl)は除外。確実判定用に著者/題も付す。
出力: data/seeds/dedup-candidates.tsv + .cache/_dedup_index.json
"""
import sys, json, re, unicodedata, yaml
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent

def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''
def hk(s): return re.sub(r'[ぁ-ん]', lambda m: chr(ord(m.group())+0x60), s)
def naz(s): return hk(re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-/／∥0-9０-９]', '', unicodedata.normalize('NFKC', str(s or '')))).lower()

# 既処理(alias済 + 本セッションdedup/aliasされたslug)を除外
done = set()
af = ROOT/'data/seeds/dup-merge-alias.yml'
if af.exists():
    a = yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    done |= set(a.keys())
opf = ROOT/'data/seeds/intake-manifest/operations.jsonl'
if opf.exists():
    for l in opf.open(encoding='utf-8'):
        try: o = json.loads(l)
        except: continue
        if o.get('slug') and o.get('op_source') in ('isbn-dup', 'dup-merge', 'samename-dedup', 'dup-strip'):
            done.add(o['slug'])

print('LIVE 走査...', flush=True)
SRC = ROOT/'data/manga.v2'
info = {}
n = 0
for fp in SRC.glob('*.yml'):
    try: d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    except: continue
    if not isinstance(d, dict): continue
    sl = d.get('slug') or fp.stem
    ibs = frozenset(to13(v.get('isbn13')) for e in (d.get('editions') or []) for v in (e.get('volumes') or []) if to13(v.get('isbn13')))
    if not ibs: continue
    au = '/'.join(naz(a.get('name')) for a in (d.get('authors') or []) if a.get('name'))
    info[sl] = {'ibs': ibs, 'au': au, 'title': d.get('title'), 'nau': [a.get('name') for a in (d.get('authors') or [])]}
    n += 1
    if n % 15000 == 0: print(f'  {n}', flush=True)
print(f'  {n}ページ走査', flush=True)

# 1) 完全一致ISBN集合 (最強=確実重複)
byset = defaultdict(list)
for sl, m in info.items():
    byset[m['ibs']].append(sl)
exact = [(sorted(slugs), ibs) for ibs, slugs in byset.items() if len(slugs) >= 2]

# 2) 高重複(片方が他方の部分集合 or Jaccard>=0.6) = slug表記揺れ/欠け巻の重複候補
#    全対は重いので、ISBNを共有するslug対のみ検査
isbn2slug = defaultdict(set)
for sl, m in info.items():
    for ib in m['ibs']: isbn2slug[ib].add(sl)
pairs = set()
for ib, slugs in isbn2slug.items():
    if len(slugs) < 2 or len(slugs) > 12: continue
    sl = sorted(slugs)
    for i in range(len(sl)):
        for j in range(i+1, len(sl)):
            pairs.add((sl[i], sl[j]))
overlap = []
seen_exact = set(tuple(s) for s, _ in exact)
for a, b in pairs:
    A, B = info[a]['ibs'], info[b]['ibs']
    inter = len(A & B)
    if not inter: continue
    jac = inter/len(A | B)
    sub = (A <= B or B <= A)
    if A == B: continue  # exactで拾う
    if sub or jac >= 0.6:
        overlap.append((a, b, inter, len(A), len(B), round(jac, 2), sub))

out = ROOT/'data/seeds/dedup-candidates.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('# === EXACT (同一ISBN集合=確実重複) ===\n')
    f.write('type\tslugs\tn_isbn\tauthors\ttitles\n')
    for slugs, ibs in sorted(exact, key=lambda x: -len(x[1])):
        if all(s in done for s in slugs): continue
        aus = ' || '.join('/'.join(info[s]['nau']) for s in slugs)
        tis = ' || '.join(str(info[s]['title']) for s in slugs)
        f.write(f"EXACT\t{','.join(slugs)}\t{len(ibs)}\t{aus}\t{tis}\n")
    f.write('# === OVERLAP (高重複=表記揺れ/欠け巻 重複候補、要確認) ===\n')
    for a, b, inter, na, nb, jac, sub in sorted(overlap, key=lambda x: -x[5]):
        if a in done or b in done: continue
        f.write(f"OVERLAP\t{a},{b}\tinter{inter}/{na}/{nb}\tjac{jac}{'/subset' if sub else ''}\t{info[a]['nau']}|{info[b]['nau']}\t{info[a]['title']}|{info[b]['title']}\n")
json.dump({'exact_groups': len([g for g in exact if not all(s in done for s in g[0])]),
           'overlap_pairs': len([1 for a,b,*_ in overlap if a not in done and b not in done])},
          open(ROOT/'.cache/_dedup_index.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f'EXACT群 {len(exact)} / OVERLAP対 {len(overlap)} → {out}')
