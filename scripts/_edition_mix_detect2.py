#!/usr/bin/env python3
"""
版混在検出(精密版・調査only): standard 版の中に 種1(metadata101)の実出版社名が2社以上ある作品。
= 記号(登録者)違いの偽陽性(同一社が複数記号)を排し、本当に別社の巻が混ざったものだけ。
出力: data/seeds/edition-mix-candidates2.csv + 集計。 本番変更なし。
"""
import yaml,csv,json,time
from pathlib import Path
from collections import Counter
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
ROOT=Path(__file__).resolve().parent.parent

def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict):
                for kk in ('@value','name','schema:name','rdfs:label'):
                    if x.get(kk): return x[kk] if isinstance(x[kk],str) else first(x[kk])
        return None
    if isinstance(v,dict):
        for kk in ('@value','name','schema:name','rdfs:label'):
            if v.get(kk): return first(v[kk])
        return None
    return v
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    t0=time.time()
    print('種1 metadata101 ロード中...',flush=True)
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    isbn2pub={}
    for r in g:
        if 'Book' not in str(r.get('@type','')): continue
        ib=to13(first(r.get('schema:isbn')))
        if not ib: continue
        pub=first(r.get('schema:publisher'))
        if pub: isbn2pub[ib]=str(pub).strip()
    print(f'ISBN→出版社: {len(isbn2pub):,} [{time.time()-t0:.0f}s]',flush=True)

    rows=[]; mix_works=0; mix_gap=0
    M=ROOT/'data'/'manga.v2'
    for i,fp in enumerate(M.glob('*.yml')):
        if i%15000==0 and i: print(f'  scan ...{i} [{time.time()-t0:.0f}s]',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        eds=d.get('editions') or []
        tot=sum(len(e.get('volumes') or []) for e in eds)
        cov=sum(1 for e in eds for v in (e.get('volumes') or []) if v.get('cover_url'))
        hagaake = tot>0 and 0<cov<tot
        for e in eds:
            if e.get('type')!='standard': continue
            pubc=Counter(); bypub={}
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                p=isbn2pub.get(ib)
                if not p: continue
                pubc[p]+=1; bypub.setdefault(p,[]).append(v.get('number'))
            if len(pubc)>=2:
                mix_works+=1
                if hagaake: mix_gap+=1
                maj=pubc.most_common(1)[0][0]
                minors=[p for p in pubc if p!=maj]
                minvols=sorted((n for p in minors for n in bypub[p] if n is not None))[:30]
                rows.append([d.get('slug'),d.get('title'),len(e.get('volumes') or []),
                             ' | '.join(f'{p}:{pubc[p]}' for p,_ in pubc.most_common()),
                             maj, ';'.join(f'{p}={bypub[p]}' for p in minors)[:140],
                             'yes' if hagaake else 'no', str(minvols)])
    out=ROOT/'data'/'seeds'/'edition-mix-candidates2.csv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(['slug','title','std_vols','publishers','majority','minority_detail','hagaake','minority_volumes'])
        for r in sorted(rows,key=lambda x:-x[2]): w.writerow(r)
    print(f'\n=== 版混在(精密=実出版社2社以上 in standard)===')
    print(f'候補作品: {mix_works:,}(うち歯抜け {mix_gap:,})')
    print(f'→ {out}')
    print('-- サンプル(巻数多い順12)--')
    for r in sorted(rows,key=lambda x:-x[2])[:12]:
        print(f'  {str(r[1])[:20]:20s} std{r[2]:>3} [{r[3][:46]}] minor:{r[5][:34]}')

if __name__=='__main__': main()
