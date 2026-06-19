#!/usr/bin/env python3
"""
取り違え是正 段階3=削除(慎重・可逆)。192ラベル作から誤ISBNを除去。
★削除前検証: 各誤ISBNが「別作(新規作成 or 既存 or B欧米=保全不要)に在る」ことを確認。
- C退避ラベルは中身未保全なので除外(消さない)。
- 保全されてない誤ISBNがあれば flag して**消さない**。
dry-run(既定) / --apply(backup+changelog)。
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
    # 誤ISBN per label + B/C 集合
    wrong=defaultdict(set)
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-source-table.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if len(x)<7 or x[6]!='TORICHIGAE' or (aset(x[3]) & aset(x[5])): continue
        wrong[x[1]].add(x[0])
    def load_slugs(fn):
        p=ROOT/'data'/'seeds'/fn; out=set()
        if p.exists():
            for ln in p.read_text(encoding='utf-8').splitlines():
                if ln.strip(): out.add(ln.split('\t')[0])
        return out
    B=load_slugs('torichigae-routeB.tsv'); C=load_slugs('torichigae-routeC.tsv')
    print(f'ラベル {len(wrong)} / B(欧米){len(B)} / C(退避除外){len(C)}',flush=True)
    # DB全 isbn->slugs (新規作成含む)
    isbn2slugs=defaultdict(set); slug_total=defaultdict(int)
    for fp in sorted((ROOT/'data'/'manga.v2').glob('*.yml')):
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        sl=d.get('slug')
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                slug_total[sl]+=1
                ib=to13(v.get('isbn13'))
                if ib: isbn2slugs[ib].add(sl)
    # 検証 + 削除計画
    deletable=defaultdict(set); flagged=[]
    for slug,isbns in wrong.items():
        if slug in C: continue   # 退避=消さない
        scope_out = slug in B
        for ib in isbns:
            others=isbn2slugs[ib]-{slug}
            if others or scope_out: deletable[slug].add(ib)   # 保全済 or 欧米scope外
            else: flagged.append((slug,ib))
    ndel=sum(len(v) for v in deletable.values())
    print(f'\n=== 削除前検証 ===')
    print(f'  削除可(保全確認済 or 欧米): {ndel} ISBN / {len(deletable)} 作')
    print(f'  ★未保全=flag(消さない): {len(flagged)}')
    for sl,ib in flagged[:15]: print(f'    {sl} {ib}')
    if flagged:
        print('  → 未保全ありのため、その作はskip(消さない)')
    if not APPLY:
        print('\n(dry-run。 --apply で削除実行)'); return
    bak=ROOT/'.cache'/f'toridel-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    lf=(ROOT/'data'/'seeds'/'torichigae-delete-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    nfix=0; emptied=[]
    for slug,isbns in deletable.items():
        for base in ('data/manga.v2','.preview-data/manga'):
            fp=ROOT/base/f'{slug}.yml'
            if not fp.exists(): continue
            d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
            shutil.copy2(fp,bak/(base.replace('/','_')+'__'+slug+'.yml'))
            rem=[]
            for e in (d.get('editions') or []):
                kept=[]
                for v in (e.get('volumes') or []):
                    if to13(v.get('isbn13')) in isbns: rem.append(to13(v.get('isbn13')))
                    else: kept.append(v)
                e['volumes']=kept
            d['editions']=[e for e in (d.get('editions') or []) if e.get('volumes')]
            fp.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            if base=='data/manga.v2':
                nfix+=1
                if not d.get('editions'): emptied.append(slug)
                lf.write(json.dumps({'slug':slug,'removed':sorted(isbns),'emptied':not d.get('editions'),'at':st},ensure_ascii=False)+'\n')
    lf.close()
    (ROOT/'data'/'seeds'/'torichigae-emptied-labels.txt').write_text('\n'.join(emptied),encoding='utf-8')
    print(f'\n適用: {nfix}作から誤ISBN除去 / 空化ラベル {len(emptied)}(→RE_ISBN対象)。 backup={bak}')

if __name__=='__main__': main()
