#!/usr/bin/env python3
"""
同名(残り)の調査(read-only): 巻番号の重なり/ISBN帯/年で 分裂vs別版vs別作 を判定。
- 巻番号が相補(重なり小)+同出版社帯 → SPLIT(分裂=統合候補)
- 巻番号が重複(各々vol1から) → EDITION(別版=触らない)
- 副題違い(元/外伝/SIDE/i) → SPINOFF/別作(触らない)
出力: data/seeds/samename-investigate.tsv
"""
import sys,csv,re
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def info(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    if not fp.exists(): return None
    d=yaml.safe_load(fp.read_text(encoding='utf-8'))
    vols=set(); bands=set(); yrs=set()
    for e in d.get('editions',[]):
        for v in e.get('volumes',[]):
            if v.get('number'): vols.add(int(v['number']))
            ib=to13(v.get('isbn13'))
            if ib: bands.add(ib[3:10])  # 出版者記号帯(978-4-XXXXX)
            rd=str(v.get('release_date') or '')
            m=re.match(r'(\d{4})',rd)
            if m: yrs.add(int(m.group(1)))
    return {'title':d.get('title'),'sub':d.get('subtitle',''),'vols':vols,'bands':bands,'yrs':yrs,
            'n':sum(len(e.get('volumes',[])) for e in d.get('editions',[]))}

def main():
    rows=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'samename-audit.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='title': continue
        title=x[0]; slugs=[p.split('(')[0].strip() for p in x[2].split('|')]
        I={s:info(s) for s in slugs}; I={s:i for s,i in I.items() if i}
        if len(I)<2: continue
        sl=list(I)
        # 巻番号の重なり(代表ペア)
        vol_overlap=0; tot=0
        for i in range(len(sl)):
            for j in range(i+1,len(sl)):
                a,b=I[sl[i]]['vols'],I[sl[j]]['vols']
                if a and b: vol_overlap=max(vol_overlap,len(a&b)/min(len(a),len(b))); tot+=1
        # title(slugから副題違い検出): titleは同じなので、巻と帯で判定
        allbands=set();
        for s in sl: allbands|=I[s]['bands']
        same_band = len(allbands)<=1
        if len(I)>3:
            verdict='FAMILY(多数=要個別)'
        elif vol_overlap<0.2 and same_band:
            verdict='SPLIT?(巻相補+同帯=分裂候補)'
        elif vol_overlap>=0.5:
            verdict='EDITION/別作(巻重複=各々完結)'
        else:
            verdict='AMBIG(要目視)'
        def e1(s):
            v=I[s]['vols']; vr=(str(min(v))+'-'+str(max(v))) if v else '?'
            return s+'(v'+vr+','+str(I[s]['n'])+'冊,帯'+str(sorted(I[s]['bands'])[:2])+','+str(sorted(I[s]['yrs'])[:1])+')'
        ent=' | '.join(e1(s) for s in sl)
        rows.append([title,verdict,round(vol_overlap,2),ent])
    rows.sort(key=lambda r:r[1])
    with open(ROOT/'data'/'seeds'/'samename-investigate.tsv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['title','判定','巻重複','エントリ(巻範囲,冊,ISBN帯,年)'])
        for r in rows: w.writerow(r)
    from collections import Counter
    print('同名調査:',dict(Counter(r[1] for r in rows)))
    for v in ('SPLIT?(巻相補+同帯=分裂候補)','EDITION/別作(巻重複=各々完結)','AMBIG(要目視)','FAMILY(多数=要個別)'):
        sub=[r for r in rows if r[1]==v]
        print(f'-- {v} ({len(sub)}) --')
        for r in sub[:12]: print(f'  「{r[0][:14]}」重複{r[2]} {r[3][:80]}')

if __name__=='__main__': main()
