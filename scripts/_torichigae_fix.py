#!/usr/bin/env python3
"""
本物の取り違え427 ISBNを誤った作品から除去(慎重・可逆)。
- TORICHIGAE(題も著者も違う=ISBNが別作に付与)を再導出(著者サフィックス除去でFP排除)。
- 各誤ISBNが「正しい作品側(別slug)にも在るか」を確認=在れば除去は安全(消失でない)。
- 除去後に空になる作を flag。
- dry-run(既定) / --apply(backup+changelog)。 本番不変は dry時。
"""
import sys,csv,re,json,time,shutil,unicodedata
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
APPLY='--apply' in sys.argv
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def norm1(p):
    p=unicodedata.normalize('NFKC',p); p=re.sub(r'[（(].*?[）)]','',p)
    p=re.sub(r'^(team|チーム)','',p,flags=re.I); p=re.sub(r'[\s　・。.\]\[]','',p)
    return hk(p).lower()
def aset(s): return set(norm1(x) for x in re.split(r'[;／/、,]',s) if len(norm1(x))>=2)
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    # 427 = TORICHIGAE かつ サフィックス除去後も著者重複なし
    wrong=defaultdict(set)   # slug -> set(誤ISBN)
    truen={}                 # isbn -> (真題,真著)
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-source-table.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if len(x)<7 or x[6]!='TORICHIGAE': continue
        if aset(x[3]) & aset(x[5]): continue   # 同一著者(FP)除外
        wrong[x[1]].add(x[0]); truen[x[0]]=(x[4],x[5])
    allwrong=set(i for s in wrong.values() for i in s)
    print(f'対象: {sum(len(v) for v in wrong.values())} ISBN / {len(wrong)} 作品',flush=True)
    # DB全体の isbn->slugs + 各slugの巻数
    isbn2slugs=defaultdict(set); slug_total=defaultdict(int)
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%20000==0 and i: print(f'  scan {i}',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        sl=d.get('slug')
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                slug_total[sl]+=1
                ib=to13(v.get('isbn13'))
                if ib: isbn2slugs[ib].add(sl)
    # 分析
    safe=lose=0; empties=[]
    for slug,isbns in wrong.items():
        rem=slug_total[slug]-len(isbns)
        if rem<=0: empties.append((slug,len(isbns)))
        for ib in isbns:
            others=isbn2slugs[ib]-{slug}
            if others: safe+=1
            else: lose+=1
    print(f'\n=== dry分析 ===')
    print(f'  除去ISBN総数: {len(allwrong)}')
    print(f'  うち正しい作品側(別slug)にも在る=安全除去: {safe}')
    print(f'  どこにも残らない(除去で消失=要再付与判断): {lose}')
    print(f'  除去後に空になる作: {len(empties)}')
    for sl,n in sorted(empties,key=lambda z:-z[1])[:12]:
        t=truen.get(next(iter(wrong[sl])),('',''))
        print(f'    {sl[:26]:26s} 全{slug_total[sl]}巻 全部誤ISBN→空 (真:{t[1][:10]})')
    if not APPLY:
        print('\n(dry-run。 --apply で除去実行: backup+changelog)'); return
    # 適用: 誤ISBNの巻を除去
    bak=ROOT/'.cache'/f'torichigae-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    log=ROOT/'data'/'seeds'/'torichigae-fix-changelog.jsonl'; lf=log.open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    nfix=0
    for slug,isbns in wrong.items():
        for base in ('data/manga.v2','.preview-data/manga'):
            fp=ROOT/base/f'{slug}.yml'
            if not fp.exists(): continue
            d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
            shutil.copy2(fp,bak/(base.replace('/','_')+'__'+slug+'.yml'))
            removed=[]
            for e in (d.get('editions') or []):
                kept=[]
                for v in (e.get('volumes') or []):
                    if to13(v.get('isbn13')) in isbns: removed.append(to13(v.get('isbn13')))
                    else: kept.append(v)
                e['volumes']=kept
            d['editions']=[e for e in (d.get('editions') or []) if e.get('volumes')]
            fp.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            if base=='data/manga.v2':
                lf.write(json.dumps({'slug':slug,'removed_isbns':removed,'true':truen.get(removed[0]) if removed else None,'at':st},ensure_ascii=False)+'\n')
                nfix+=1
    lf.close()
    print(f'\n適用: {nfix}作から誤ISBN除去。 backup={bak}')

if __name__=='__main__': main()
