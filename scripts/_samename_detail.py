#!/usr/bin/env python3
"""
同名40の精査(read-only): 各エントリのISBN集合を突合。
COPY(ISBN集合ほぼ一致=重複)/SPLIT(著者同・巻番号で補完関係)/EDITION(disjoint=別版)/HOMONYM(著者違い既除外)。
出力: data/seeds/samename-detail.tsv
"""
import sys,csv,re
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    if not fp.exists(): return None
    d=yaml.safe_load(fp.read_text(encoding='utf-8'))
    isbns=set(); vols=set()
    for e in d.get('editions',[]):
        for v in e.get('volumes',[]):
            ib=to13(v.get('isbn13'))
            if ib: isbns.add(ib)
            if v.get('number'): vols.add(v.get('number'))
    au=set(a.get('name') for a in (d.get('authors') or []))
    return {'isbns':isbns,'vols':vols,'au':au,'y':d.get('year_started'),'n':sum(len(e.get('volumes',[])) for e in d.get('editions',[]))}

def main():
    rows=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'samename-audit.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='title': continue
        title=x[0]; slugs=[p.split('(')[0].strip() for p in x[2].split('|')]
        infos={s:load(s) for s in slugs}; infos={s:i for s,i in infos.items() if i}
        if len(infos)<2: continue
        sl=list(infos)
        # 全ペアのISBN関係(代表=最大ペア)
        verdict='?'; detail=''
        # 全ISBN集合
        allisbn=[infos[s]['isbns'] for s in sl]
        # COPY判定: 2つのISBN集合が高一致
        best=('',0)
        for i in range(len(sl)):
            for j in range(i+1,len(sl)):
                a,b=infos[sl[i]]['isbns'],infos[sl[j]]['isbns']
                if not a or not b: continue
                ov=len(a&b)/max(1,min(len(a),len(b)))
                if ov>best[1]: best=(f'{sl[i]}∩{sl[j]}',ov)
        anyisbn=any(infos[s]['isbns'] for s in sl)
        if not anyisbn:
            verdict='NO_ISBN'; detail='全ISBN無=判定不可'
        elif best[1]>=0.5:
            verdict='COPY'; detail=f'{best[0]} ISBN一致{best[1]:.0%}'
        else:
            # 巻番号が相互補完(disjoint vols)ならSPLIT、重なるならEDITION
            verdict='SPLIT/EDITION'; detail=f'ISBN最大一致{best[1]:.0%}'
        entry=' | '.join(s+'('+str(infos[s]['n'])+'巻,'+str(infos[s]['y'])+')' for s in sl)
        rows.append([title,verdict,detail,entry])
    rows.sort(key=lambda r:r[1])
    with open(ROOT/'data'/'seeds'/'samename-detail.tsv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['title','判定','詳細','エントリ'])
        for r in rows: w.writerow(r)
    from collections import Counter
    print('同名40精査:',dict(Counter(r[1] for r in rows)))
    for v in ('COPY','NO_ISBN','SPLIT/EDITION'):
        print(f'-- {v} --')
        for r in [r for r in rows if r[1]==v][:14]: print(f'  「{r[0][:16]}」{r[2]}  {r[3][:60]}')

if __name__=='__main__': main()
