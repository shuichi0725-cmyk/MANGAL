#!/usr/bin/env python3
"""
★題でなくISBN集合で重複検出(怖い本三重複型=題違いの複製を捕捉)。
- EXACT: ISBN集合が完全一致の複数作=複製(dedup対象)
- HIGH: ISBN集合の重なりが高い(片方が他方のsubset等)=分裂/版違い
題normalizeで漏れる重複を根本検出。 read-only。 出力: data/seeds/isbn-set-dup.tsv
"""
import sys,glob,os,csv
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def main():
    work_isbns={}; work_title={}; work_au={}
    isbn2works=defaultdict(set)
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%15000==0 and i: print(f'  ...{i}',flush=True)
        try: d=yaml.safe_load(open(fp,encoding='utf-8'))
        except: continue
        if not isinstance(d,dict): continue
        sl=d.get('slug'); isb=set()
        for e in d.get('editions',[]):
            for v in e.get('volumes',[]):
                ib=to13(v.get('isbn13'))
                if ib: isb.add(ib)
        if len(isb)<2: continue   # ISBN1個以下は判定不可
        work_isbns[sl]=isb; work_title[sl]=str(d.get('title','')); work_au[sl]=tuple(a.get('name') for a in (d.get('authors') or []))
        for ib in isb: isbn2works[ib].add(sl)
    # EXACT: 同一frozenset
    byset=defaultdict(list)
    for sl,isb in work_isbns.items(): byset[frozenset(isb)].append(sl)
    exact=[v for v in byset.values() if len(v)>1]
    # HIGH: ISBN共有で連結(exact以外)。 共有ペアを集計
    exact_slugs=set(s for g in exact for s in g)
    pair=defaultdict(int)
    for ib,ws in isbn2works.items():
        ws=[w for w in ws if w not in exact_slugs]
        ws=sorted(ws)
        for a in range(len(ws)):
            for b in range(a+1,len(ws)):
                pair[(ws[a],ws[b])]+=1
    high=[]
    for (a,b),n in pair.items():
        mn=min(len(work_isbns[a]),len(work_isbns[b]))
        if n>=2 and n>=0.5*mn: high.append((a,b,n,mn))
    high.sort(key=lambda x:-x[2])
    out=ROOT/'data'/'seeds'/'isbn-set-dup.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['type','slugs','titles','ISBN数'])
        for g in sorted(exact,key=lambda x:-len(work_isbns[x[0]])):
            w.writerow(['EXACT(完全複製)',' | '.join(g),' | '.join(work_title[s] for s in g),len(work_isbns[g[0]])])
        for a,b,n,mn in high:
            w.writerow(['HIGH(高重なり)',a+' | '+b,work_title[a]+' | '+work_title[b],f'{n}/{mn}'])
    print(f'\n★ISBN集合 重複検出:')
    print(f'  EXACT(完全複製・題違い含む): {len(exact)}グループ / {sum(len(g) for g in exact)}作')
    print(f'  HIGH(高重なり=分裂/版違い): {len(high)}ペア')
    print('-- EXACT サンプル(ISBN多い順) --')
    for g in sorted(exact,key=lambda x:-len(work_isbns[x[0]]))[:18]:
        print(f'  [{len(work_isbns[g[0]])}巻] '+' = '.join(f'{s}「{work_title[s][:10]}」' for s in g))

if __name__=='__main__': main()
