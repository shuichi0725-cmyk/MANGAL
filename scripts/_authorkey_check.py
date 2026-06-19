#!/usr/bin/env python3
"""
著者キー逆引きで NOT_FOUND/AUTHOR_MISMATCH を局所救済(API不要)。
cm104+楽天種から 著者token→題core集合 を作り、対象作の著者の作品一覧に
題が近い(LCS高)ものが在れば CONFIRMED_BY_AUTHOR(=実在・身元OK)とする。
出力: data/seeds/authorkey-confirmed.tsv
"""
import sys,json,csv,re,unicodedata
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def tcore(s):
    s=zen(str(s or '')); s=unicodedata.normalize('NFKC',s); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'[．.]\s*\d+\s*$','',s); s=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
    return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def names(s):
    if isinstance(s,list):
        s=' / '.join(x if isinstance(x,str) else (x.get('@value','') if isinstance(x,dict) and x.get('@language')!='ja-hrkt' else '') for x in s)
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p); p=re.sub(r'[\s　・。.]','',p)
        if len(p)>=2: out.add(hk(p).lower())
    return out
def lcs(a,b):
    if not a or not b: return 0
    pr=[0]*(len(b)+1); best=0
    for i in range(1,len(a)+1):
        cu=[0]*(len(b)+1)
        for j in range(1,len(b)+1):
            if a[i-1]==b[j-1]: cu[j]=pr[j-1]+1; best=max(best,cu[j])
        pr=cu
    return best
def sim(a,b):
    if not a or not b: return False
    if a in b or b in a: return True
    return lcs(a,b)>=4 and lcs(a,b)>=0.6*min(len(a),len(b))

def main():
    print('著者→題core 索引構築...',flush=True)
    a2t=defaultdict(set)
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata104.json',encoding='utf-8'))
    g=g.get('@graph',g) if isinstance(g,dict) else g
    def cnm(r):
        v=r.get('ma:seriesName') or r.get('schema:name'); return v[0] if isinstance(v,list) else v
    for r in g:
        tc=tcore(cnm(r))
        if tc:
            for a in names(r.get('schema:creator')): a2t[a].add(tc)
    seed=ROOT/'.cache'/'rakuten-isbn.jsonl'
    if seed.exists():
        for line in seed.open(encoding='utf-8'):
            try: it=json.loads(line).get('item') or {}
            except: continue
            tc=tcore(it.get('title'))
            if tc:
                for a in names(it.get('author')): a2t[a].add(tc)
    print(f'著者token {len(a2t):,} [対象照合]',flush=True)
    rows=[]; conf=0; tot=0
    with open(ROOT/'data'/'seeds'/'identity-check.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            tot+=1
            slug,title,au_s,_,st=x
            au=set(t for t in au_s.split(';') if t)
            tc=tcore(title)
            cand=set()
            for a in au: cand|=a2t.get(a,set())
            matched=next((c for c in cand if sim(tc,c)),None)
            if matched:
                conf+=1; rows.append([slug,title,au_s,matched,st])
    out=ROOT/'data'/'seeds'/'authorkey-confirmed.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','authors','matched_title_core(著者の作品)','orig_status'])
        for r in rows: w.writerow(r)
    from collections import Counter
    byst=Counter(r[4] for r in rows)
    print(f'\n=== 著者キー逆引き救済 ===')
    print(f'対象(OK以外){tot:,} → 著者の作品一覧に題近似あり=実在確定 {conf:,}')
    print(f'  内訳: {dict(byst)}')
    print('-- 救済サンプル --')
    for r in rows[:14]: print(f'  [{r[4]}] {r[0][:24]:24s}「{r[1][:14]}」著[{r[2][:14]}] ≈ 著者作「{r[3][:14]}」')

if __name__=='__main__': main()
