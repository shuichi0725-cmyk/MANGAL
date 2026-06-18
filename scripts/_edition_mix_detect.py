#!/usr/bin/env python3
"""
版混在検出(調査only): 1つの standard 版の中に 出版者記号(ISBN登録者)が2種以上ある作品を検出。
= 別レーベルの巻が standard に紛れ込んだ候補(北斗の拳 集英社08 + 新潮社10 型)。
日本ISBN(978-4-…)の登録者グループ長を正規ルールで判定して記号を抽出。
出力: data/seeds/edition-mix-candidates.csv(1行=候補作) + 集計。 本番変更なし。
"""
import yaml,csv,time
from pathlib import Path
from collections import Counter
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
ROOT=Path(__file__).resolve().parent.parent

# 主要出版者記号→社名(表示用・既知のみ)
PUB={'08':'集英社','06':'講談社','09':'小学館','10':'新潮社','04':'KADOKAWA/角川','12':'中央公論',
     '7575':'スクウェアエニックス','7580':'白泉社','8401':'一迅社','403':'秋田書店','253':'秋田書店',
     '592':'白泉社','7986':'�003','86':'(小)','785':'少年画報社','199':'徳間','19':'徳間'}

def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() and s.startswith('9784') else ''
def registrant(isbn):
    rest=isbn[4:]  # 9桁 = 登録者+書名+チェック
    d2=int(rest[:2])
    ln = 2 if d2<=19 else 3 if d2<=69 else 4 if d2<=84 else 5 if d2<=89 else 6 if d2<=94 else 7
    return rest[:ln]

def main():
    M=ROOT/'data'/'manga.v2'; t0=time.time()
    rows=[]; mix_works=0; mix_gap=0
    for i,fp in enumerate(M.glob('*.yml')):
        if i%15000==0 and i: print(f'  ...{i} [{time.time()-t0:.0f}s]',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        eds=d.get('editions') or []
        # 歯抜け判定(全edition横断)
        tot=sum(len(e.get('volumes') or []) for e in eds)
        cov=sum(1 for e in eds for v in (e.get('volumes') or []) if v.get('cover_url'))
        hagaake = tot>0 and 0<cov<tot
        for e in eds:
            if e.get('type')!='standard': continue
            regs=Counter()
            byreg={}
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                if not ib: continue
                r=registrant(ib); regs[r]+=1; byreg.setdefault(r,[]).append(v.get('number'))
            if len(regs)>=2:
                mix_works+=1
                if hagaake: mix_gap+=1
                maj=regs.most_common(1)[0][0]
                minors=[r for r in regs if r!=maj]
                minvols=sorted(n for r in minors for n in byreg[r] if n is not None)[:20]
                rows.append([d.get('slug'),d.get('title'),len(e.get('volumes') or []),
                             '|'.join(f'{r}:{regs[r]}({PUB.get(r,r)})' for r,_ in regs.most_common()),
                             maj+'('+PUB.get(maj,maj)+')',
                             ';'.join(f'{PUB.get(r,r)}={byreg[r]}' for r in minors)[:120],
                             'yes' if hagaake else 'no', str(minvols)])
    out=ROOT/'data'/'seeds'/'edition-mix-candidates.csv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(['slug','title','std_vols','registrants','majority','minority_detail','hagaake','minority_volumes'])
        for r in sorted(rows,key=lambda x:-x[2]): w.writerow(r)
    print(f'\n=== 版混在検出(standard版に出版者記号2種以上)===')
    print(f'候補作品: {mix_works:,}(うち歯抜け {mix_gap:,})')
    print(f'→ {out}')
    print('-- サンプル(巻数多い順10)--')
    for r in sorted(rows,key=lambda x:-x[2])[:10]:
        print(f'  {str(r[1])[:22]:22s} std{r[2]} 記号[{r[3][:40]}] minor:{r[5][:40]}')

if __name__=='__main__': main()
