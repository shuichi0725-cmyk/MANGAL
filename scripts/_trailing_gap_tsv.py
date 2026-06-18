#!/usr/bin/env python3
"""
巻末型 歯抜け(末尾の巻だけ画像なし=北斗の拳28-30型)を検出してTSV出力。
定義(standard版): 画像ありの巻の最大番号 < 画像なしの巻の最小番号 = 末尾が連続欠け。
出力: data/seeds/trailing-cover-gaps.tsv (本番変更なし)
"""
import yaml,csv,time
from pathlib import Path
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
ROOT=Path(__file__).resolve().parent.parent
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    M=ROOT/'data'/'manga.v2'; t0=time.time(); rows=[]
    for i,fp in enumerate(M.glob('*.yml')):
        if i%15000==0 and i: print(f'  ...{i} [{time.time()-t0:.0f}s]',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        for e in (d.get('editions') or []):
            if e.get('type')!='standard': continue
            cov_n=[]; unc=[]   # (num) covered / (num,isbn) uncovered
            for v in (e.get('volumes') or []):
                n=v.get('number')
                if not isinstance(n,(int,float)): continue
                if v.get('cover_url'): cov_n.append(n)
                else: unc.append((n,to13(v.get('isbn13'))))
            if not cov_n or not unc: continue
            umin=min(n for n,_ in unc); umax=max(n for n,_ in unc); cmax=max(cov_n)
            if umin>cmax:  # 末尾連続欠け(画像ありの後ろに欠けが続く)
                mvols=sorted(n for n,_ in unc)
                misbn=[ib for _,ib in sorted(unc) if ib]
                rows.append([d.get('slug'),d.get('title'),len(e.get('volumes') or []),
                             len(cov_n),len(unc),int(umin),
                             ','.join(str(int(x)) for x in mvols),
                             ','.join(misbn)])
            break  # standard は1つ想定
    out=ROOT/'data'/'seeds'/'trailing-cover-gaps.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['slug','title','std_vols','covered','missing','gap_start_vol','missing_volumes','missing_isbns'])
        for r in sorted(rows,key=lambda x:-x[4]): w.writerow(r)  # 欠け数多い順
    miss=sum(r[4] for r in rows)
    print(f'\n=== 巻末型歯抜け(末尾連続欠け in standard)===')
    print(f'作品: {len(rows):,} / 欠け巻: {miss:,}')
    print(f'→ {out}')
    print('-- サンプル(欠け数多い順10)--')
    for r in sorted(rows,key=lambda x:-x[4])[:10]:
        print(f'  {str(r[1])[:24]:24s} 全{r[2]:>3}巻 画像{r[3]}/欠{r[4]} (巻{r[5]}以降)')

if __name__=='__main__': main()
