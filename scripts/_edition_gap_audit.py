#!/usr/bin/env python3
"""
奇子型(版違い混在)検出: 1つのedition内で巻の発売日が極端に開く=異版混在の疑い。
特に「vol1(最小番号)だけ異様に古い」(奇子=上1973 vs 全集1981)を主signalに。
読み取りのみ。 出力: data/seeds/edition-gap-audit.tsv
"""
import sys,re,glob
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def yr(s):
    m=re.match(r'(\d{4})',str(s or '')); return int(m.group(1)) if m else None
THRESH=5   # 年。 これ以上の飛び=要チェック

def main():
    rows=[]
    files=sorted((ROOT/'data'/'manga.v2').glob('*.yml'))
    for i,fp in enumerate(files):
        if i%15000==0 and i: print(f'  ...{i}',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        for e in (d.get('editions') or []):
            vs=[v for v in (e.get('volumes') or [])]
            if len(vs)<2: continue
            vs=sorted(vs,key=lambda v:(v.get('number') or 0))
            yrs=[(v.get('number'),yr(v.get('release_date'))) for v in vs]
            yv=[(n,y) for n,y in yrs if y]
            if len(yv)<2: continue
            # vol1(最小番号)だけ古い: 最小番号の年 vs 次の年
            n0,y0=yv[0]; n1,y1=yv[1]
            old_first = (y1-y0)>=THRESH
            # 最大連続ギャップ
            maxgap=0; gpos=''
            for a in range(len(yv)-1):
                g=yv[a+1][1]-yv[a][1]
                if g>maxgap: maxgap=g; gpos=f'v{yv[a][0]}({yv[a][1]})→v{yv[a+1][0]}({yv[a+1][1]})'
            if old_first or maxgap>=THRESH:
                pat='OLD_FIRST' if old_first else 'MID_GAP'
                isbn0=vs[0].get('isbn13'); isbnN=vs[-1].get('isbn13')
                rows.append([d.get('slug'),str(d.get('title'))[:18],e.get('type'),e.get('label',''),
                             maxgap if not old_first else (y1-y0),pat,gpos,
                             f'{y0}-{yv[-1][1]}', 'ISBN無' if not isbn0 else '', len(vs)])
    rows.sort(key=lambda r:-r[4])
    out=ROOT/'data'/'seeds'/'edition-gap-audit.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        import csv; w=csv.writer(f,delimiter='\t')
        w.writerow(['slug','title','版type','label','最大ギャップ年','pattern','飛び位置','年範囲','vol1状態','巻数'])
        for r in rows: w.writerow(r)
    from collections import Counter
    print(f'\n=== 奇子型(版内発売日ギャップ≥{THRESH}年)検出: {len(rows)} edition ===')
    print('pattern:',dict(Counter(r[5] for r in rows)))
    print('  うち OLD_FIRST(vol1だけ古い・奇子型):',sum(1 for r in rows if r[5]=='OLD_FIRST'))
    print('  うち vol1がISBN無(奇子と同型):',sum(1 for r in rows if r[8]=='ISBN無'))
    print('-- ギャップ大きい順 サンプル --')
    for r in rows[:25]:
        print(f'  {r[0][:22]:22s}「{r[1][:12]}」{r[2]}「{r[3][:8]}」{r[4]}年飛び [{r[5]}] {r[6]} {r[8]}')

if __name__=='__main__': main()
