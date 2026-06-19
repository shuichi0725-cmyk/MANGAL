#!/usr/bin/env python3
"""
ISBN誤共有17組のun-merge調査: 各組の共有ISBNが種1/楽天で実際は何の作品(題/著者)かを示す。
正しい持ち主の特定用。 read-only。
"""
import sys,json,glob,os,re
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
    return v
def main():
    print('種1+楽天ロード...',flush=True)
    s1={}; rk={}
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    for r in g:
        ib=to13(first(r.get('schema:isbn')))
        if ib: s1[ib]=(first(r.get('schema:name')) or '', first(r.get('schema:creator')) or '')
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        it=o.get('item') or {}
        if ib and it: rk[ib]=(it.get('title',''),it.get('author',''))
    print('loaded',flush=True)
    def load(slug):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        return yaml.safe_load(fp.read_text(encoding='utf-8')) if fp.exists() else None
    for line in (ROOT/'data'/'seeds'/'isbn-dup-unmerge-flag.tsv').read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        reason,slugs=line.split('\t',1); slugs=[s.strip() for s in slugs.split('|')]
        print(f'\n■[{reason}] '+' vs '.join(slugs))
        ds={s:load(s) for s in slugs}
        for s in slugs:
            d=ds[s]
            if not d: print(f'  {s}: (無)'); continue
            au=[a.get('name') for a in (d.get('authors') or [])]
            print(f'  ▸{s}「{d.get("title")}」DB著者{au} year{d.get("year_started")}')
        # 共有ISBN(最初の存在作から)
        isb=[]
        for s in slugs:
            if ds[s]:
                for e in ds[s].get('editions',[]):
                    for v in e.get('volumes',[]):
                        ib=to13(v.get('isbn13'))
                        if ib: isb.append((v.get('number'),ib))
                break
        seen=set()
        for num,ib in isb:
            if ib in seen: continue
            seen.add(ib)
            t1=s1.get(ib); rr=rk.get(ib)
            src = ('種1:'+t1[0][:22]+'/'+str(t1[1])[:12]) if t1 else (('楽天:'+rr[0][:22]+'/'+str(rr[1])[:12]) if rr else '不明')
            print(f'     v{num} {ib} = {src}')

if __name__=='__main__': main()
