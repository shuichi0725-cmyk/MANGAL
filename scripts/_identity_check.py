#!/usr/bin/env python3
"""
①漫画名×作者名チェック(ローカル・読み取りのみ)。
66k全作品の (題core × 著者) が cm104 / 楽天種 に実在するか照合。
分類: OK(題+著者一致) / AUTHOR_MISMATCH(題はあるが著者違い) / NOT_FOUND(題が無い)。
NOT_FOUND/AUTHOR_MISMATCH が ②以降の調査対象(楽天API/NDL再確認→種1原因)。
出力: data/seeds/identity-check.tsv
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
    s=re.sub(r'[．.]\s*\d+\s*$','',s)
    s=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
    return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def creator_str(v):  # cm104 schema:creator = str or list(str|{@value,@language}) → 名前のみ(読みdict除外)
    if isinstance(v,str): return v
    if isinstance(v,list):
        parts=[]
        for x in v:
            if isinstance(x,str): parts.append(x)
            elif isinstance(x,dict) and x.get('@language')!='ja-hrkt' and x.get('@value'): parts.append(x['@value'])
        return ' / '.join(parts)
    if isinstance(v,dict): return v.get('@value','') if v.get('@language')!='ja-hrkt' else ''
    return str(v or '')
def hira2kata(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def names(s):  # 著者名集合(/、; のみで分割。 ・空白は姓名内なので割らない)
    s=creator_str(s)
    if not s: return set()
    s=unicodedata.normalize('NFKC',s); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p)
        p=re.sub(r'[\s　・。.]','',p)   # 名内の区切り除去=連結
        if len(p)>=2: out.add(hira2kata(p).lower())
    return out
def concat(s):  # 連結nodelim(部分一致用)
    return ''.join(names(s))
def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
    return v

def main():
    print('cm104 ロード...',flush=True)
    idx=defaultdict(set)   # title_core -> union author tokens (複数版/作の和)
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata104.json',encoding='utf-8'))
    g=g.get('@graph',g) if isinstance(g,dict) else g
    def cnm(r):
        v=r.get('ma:seriesName') or r.get('schema:name'); return v[0] if isinstance(v,list) else v
    for r in g:
        c=tcore(cnm(r))
        if c: idx[c]|=names(r.get('schema:creator'))
    print(f'cm104 題core {len(idx):,} [楽天種マージ中]',flush=True)
    seed=ROOT/'.cache'/'rakuten-isbn.jsonl'
    if seed.exists():
        for line in seed.open(encoding='utf-8'):
            try: it=json.loads(line).get('item') or {}
            except: continue
            c=tcore(it.get('title'))
            if c: idx[c]|=names(it.get('author'))
    print(f'統合 題core {len(idx):,} [スキャン]',flush=True)
    rows=[]; from collections import Counter; cnt=Counter()
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%15000==0 and i: print(f'  ...{i}',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        tc=tcore(d.get('title'))
        au=set()
        for k in ('authors','original_authors'):
            for a in (d.get(k) or []): au|=names(a.get('name') if isinstance(a,dict) else a)
        if tc in idx:
            src=idx[tc]; sc=''.join(src); oc=''.join(au)
            hit = (au & src) or any(o in sc for o in au if len(o)>=2) or any(x in oc for x in src if len(x)>=2)
            st='OK' if (not au or hit) else 'AUTHOR_MISMATCH'
        else: st='NOT_FOUND'
        cnt[st]+=1
        if st!='OK':
            rows.append([d.get('slug'),d.get('title'),';'.join(sorted(au))[:30],
                         ';'.join(sorted(idx.get(tc,set())))[:30],st])
    out=ROOT/'data'/'seeds'/'identity-check.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','our_authors','source_authors(同題)','status'])
        for r in rows: w.writerow(r)
    ok=cnt['OK']; am=cnt['AUTHOR_MISMATCH']; nf=cnt['NOT_FOUND']
    print('\n=== ①漫画名×作者名チェック ===')
    print(f'  OK(題+著者一致): {ok:,}')
    print(f'  AUTHOR_MISMATCH(題有・著者違い): {am:,}')
    print(f'  NOT_FOUND(題が局所に無い): {nf:,}')
    print(f'  → {out}(OK以外を記録)')

if __name__=='__main__': main()
