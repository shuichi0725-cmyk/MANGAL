#!/usr/bin/env python3
"""
1作の中で巻ごとにISBN→著者(種1/楽天)が異なる=同名異作の巻が混在(JOKER型)を検出。
各作の巻ISBNの真著者を集め、共有名なしの著者グループが2つ以上→混在flag。
出力: data/seeds/intra-work-author-split.tsv
"""
import sys,json,csv,re,unicodedata,glob,os
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def names(v):
    if isinstance(v,list):
        v=' / '.join(x if isinstance(x,str) else (x.get('@value','') if isinstance(x,dict) and x.get('@language')!='ja-hrkt' else '') for x in v)
    if not v: return set()
    s=unicodedata.normalize('NFKC',str(v)); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p); p=re.sub(r'[\s　・。.]','',p)
        if len(p)>=2: out.add(hk(p).lower())
    return out
def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
    return v

def main():
    print('種1+楽天 ロード...',flush=True)
    au={}; ti={}
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    for r in g:
        ib=to13(first(r.get('schema:isbn')))
        if ib: au[ib]=names(r.get('schema:creator')); ti[ib]=first(r.get('schema:name')) or ''
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        it=o.get('item') or {}
        if ib and it and ib not in au: au[ib]=names(it.get('author')); ti[ib]=it.get('title','')
    print(f'ISBN→著者 {len(au):,} [scan]',flush=True)
    rows=[]
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%15000==0 and i: print(f'  ...{i}',flush=True)
        try: d=yaml.safe_load(open(fp,encoding='utf-8'))
        except: continue
        if not isinstance(d,dict): continue
        # 巻ごとの著者集合
        vau=[]
        for e in d.get('editions',[]):
            for v in e.get('volumes',[]):
                ib=to13(v.get('isbn13'))
                if ib and ib in au and au[ib]: vau.append((v.get('number'),au[ib],ti.get(ib,'')))
        if len(vau)<2: continue
        # 著者グループ化(共有名でunion)
        groups=[]
        for num,a,t in vau:
            placed=False
            for gg in groups:
                if gg['au'] & a: gg['au']|=a; gg['vols'].append(num); placed=True; break
            if not placed: groups.append({'au':set(a),'vols':[num],'ti':t})
        if len(groups)>=2:
            desc=' || '.join(f"{';'.join(sorted(gg['au']))[:14]}(v{sorted(x for x in gg['vols'] if x)})" for gg in groups)
            rows.append([d.get('slug'),str(d.get('title'))[:18],len(groups),desc[:80]])
    rows.sort(key=lambda r:-r[2])
    out=ROOT/'data'/'seeds'/'intra-work-author-split.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','著者グループ数','著者別巻'])
        for r in rows: w.writerow(r)
    print(f'\n★1作に複数著者混在(同名異作merge疑い): {len(rows)} 作 → {out}')
    print('-- サンプル(著者グループ多い順) --')
    for r in rows[:25]: print(f'  {r[0][:22]:22s}「{r[1][:12]}」{r[2]}著: {r[3][:60]}')

if __name__=='__main__': main()
