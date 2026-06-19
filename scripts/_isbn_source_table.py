#!/usr/bin/env python3
"""
ISBNキー 厳密比較表(種1 metadata101 + 楽天種 を権威に、本番DBの作品帰属を検証)。
各ISBNの「真の著者」(種1/楽天)が、本番DBでそのISBNが属する作品の著者と一致するか。
- 一致(AGREE) / 不一致(CONFLICT=取り違え確定) / ソース無(NO_SOURCE)。
- 著者は厳密名照合(区切り正規化+ひらがな→カナ。 曖昧LCSは使わない)。
出力: data/seeds/isbn-source-table.tsv (CONFLICT/NO_SOURCE), 集計。
"""
import sys,json,csv,re,unicodedata
from pathlib import Path
from collections import Counter
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー|company)$')
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
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
    print('種1 metadata101 ロード...',flush=True)
    s1={}   # isbn -> (title, author_names)
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    for r in g:
        ib=to13(first(r.get('schema:isbn')))
        if not ib: continue
        s1[ib]=(first(r.get('schema:name')) or '', names(r.get('schema:creator')))
    print(f'種1 ISBN {len(s1):,} [楽天種]',flush=True)
    rk={}
    seed=ROOT/'.cache'/'rakuten-isbn.jsonl'
    if seed.exists():
        for line in seed.open(encoding='utf-8'):
            try: o=json.loads(line); it=o.get('item') or {}
            except: continue
            ib=to13(o.get('isbn') or it.get('isbn'))
            if ib and it: rk[ib]=(it.get('title') or '', names(it.get('author')))
    print(f'楽天種 ISBN {len(rk):,} [DB scan]',flush=True)
    rows=[]; cnt=Counter()
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%15000==0 and i: print(f'  ...{i}',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        slug=d.get('slug'); wt=d.get('title') or ''; wa=set()
        for k in ('authors','original_authors'):
            for a in (d.get(k) or []): wa|=names(a.get('name') if isinstance(a,dict) else a)
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                if not ib: continue
                src_au=set(); src_t=''
                if ib in s1: src_au|=s1[ib][1]; src_t=src_t or s1[ib][0]
                if ib in rk: src_au|=rk[ib][1]; src_t=src_t or rk[ib][0]
                if not src_au:
                    st='NO_SOURCE'
                elif not wa:
                    st='DB_NO_AUTHOR'
                elif wa & src_au:
                    st='AGREE'
                else:
                    st='CONFLICT'
                cnt[st]+=1
                if st in ('CONFLICT',):
                    rows.append([ib,slug,wt[:18],';'.join(sorted(wa))[:20],str(src_t)[:18],';'.join(sorted(src_au))[:20]])
    out=ROOT/'data'/'seeds'/'isbn-source-table.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['isbn','db_slug','db_title','db_author','src_title(種1/楽天)','src_author'])
        for r in rows: w.writerow(r)
    print('\n=== ISBN×厳密著者照合(種1+楽天) ===')
    for k in ('AGREE','CONFLICT','NO_SOURCE','DB_NO_AUTHOR'):
        print(f'  {k}: {cnt[k]:,}')
    print(f'  → CONFLICT(取り違え確定)を {out} に記録')
    print('-- CONFLICT サンプル --')
    for r in rows[:16]: print(f'  {r[0]} {r[1][:20]:20s}「{r[2][:12]}」DB著[{r[3][:14]}] ≠ 真著[{r[5][:14]}]「{r[4][:12]}」')

if __name__=='__main__': main()
