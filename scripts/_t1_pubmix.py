#!/usr/bin/env python3
"""
T1 版混在 検出(読み取りのみ)。 種1(metadata101)の実出版社名(∥読み除去・NFKC正規化)で、
1つのstandard版に2社以上の巻がある作=真の版混在(北斗型)を抽出。 少数派巻=混入edition。
出力: data/seeds/t1-pubmix.tsv
"""
import sys,json,csv,re,unicodedata
from pathlib import Path
from collections import Counter,defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
FAMILY=[
  (('kadokawa','角川','メディアファクトリー','アスキー','エンターブレイン','富士見','中経出版','メディアワークス'),'KADOKAWA'),
  (('学研','学習研究社','gakken',),'学研'),
  (('朝日ソノラマ','朝日新聞社','朝日新聞出版','朝日新聞'),'朝日'),
  (('小学館',),'小学館'),(('集英社',),'集英社'),(('講談社',),'講談社'),
  (('秋田書店',),'秋田書店'),(('白泉社',),'白泉社'),(('新潮社',),'新潮社'),
  (('双葉社',),'双葉社'),(('リイド社',),'リイド社'),(('徳間',),'徳間'),
  (('スクウェア','スクエニ','エニックス',),'スクウェア・エニックス'),
  (('一迅社',),'一迅社'),(('芳文社',),'芳文社'),(('少年画報社',),'少年画報社'),
]
def normpub(s):
    if not s: return ''
    s=re.split(r'\s*[∥｜]\s*',str(s))[0].strip()   # 読み除去
    s=unicodedata.normalize('NFKC',s)
    s=re.sub(r'^[\[【][^\]】]*[\]】]','',s).strip()   # [発売][頒布]等タグ除去
    s=re.sub(r'\s+','',s)
    low=s.lower()
    for keys,fam in FAMILY:
        if any(k.lower() in low for k in keys): return fam
    return s
def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
    return v

def main():
    print('種1 ISBN→出版社 ロード...',flush=True)
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    i2p={}
    for r in g:
        ib=to13(first(r.get('schema:isbn')))
        if not ib: continue
        p=normpub(first(r.get('schema:publisher')))
        if p: i2p[ib]=p
    print(f'ISBN→出版社 {len(i2p):,}',flush=True)
    rows=[]
    for fp in (ROOT/'data'/'manga.v2').glob('*.yml'):
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        for e in (d.get('editions') or []):
            if e.get('type')!='standard': continue
            pc=Counter(); byp=defaultdict(list)
            for v in (e.get('volumes') or []):
                p=i2p.get(to13(v.get('isbn13')))
                if p: pc[p]+=1; byp[p].append(v.get('number'))
            if len(pc)>=2:
                maj=pc.most_common(1)[0][0]; minors=[p for p in pc if p!=maj]
                mv=sorted(x for p in minors for x in byp[p] if x is not None)
                rows.append([d.get('slug'),d.get('title'),len(e.get('volumes') or []),
                             ' | '.join(f'{p}:{pc[p]}' for p,_ in pc.most_common()),
                             maj,';'.join(f'{p}={byp[p]}' for p in minors)[:120],str(mv[:25])])
    out=ROOT/'data'/'seeds'/'t1-pubmix.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','std_vols','publishers','majority','minority_detail','minority_vols'])
        for r in sorted(rows,key=lambda x:-x[2]): w.writerow(r)
    print(f'\n真の版混在(standard内2社+): {len(rows):,} 作 → {out}')
    print('-- サンプル(巻数多い順12)--')
    for r in sorted(rows,key=lambda x:-x[2])[:12]:
        print(f'  {str(r[1])[:20]:20s} std{r[2]:>3} [{r[3][:44]}] minor:{r[5][:38]}')

if __name__=='__main__': main()
