#!/usr/bin/env python3
"""
AUTHOR_DIFF精緻化(dry・読み取り): 同ISBN同題で著者名が食い違う分を2分。
(a) 同一著者の表記違い(姓名の共通部分 or author-yomi読み一致) → 除外(誤りでない)
(b) 共通なし=我々の著者が丸ごと誤り → 真の候補(要是正・後でNDL第3確認)
出力: data/seeds/author-diff-real.tsv
"""
import sys,csv,re,unicodedata
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def names(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p); p=re.sub(r'[\s　・。.]','',p)
        if len(p)>=2: out.add(hk(p).lower())
    return out
def subov(A,B):  # 2文字以上の共通部分文字列があるか
    for a in A:
        for b in B:
            if a==b: return True
            for i in range(len(a)-1):
                if a[i:i+2] in b: return True
            for i in range(len(b)-1):
                if b[i:i+2] in a: return True
    return False

def main():
    # author-yomi 読み辞書
    yomi={}
    yf=ROOT/'data'/'seeds'/'author-yomi.yml'
    if yf.exists():
        y=yaml.safe_load(yf.read_text(encoding='utf-8')) or {}
        for k,v in (y.items() if isinstance(y,dict) else []):
            yomi[hk(unicodedata.normalize('NFKC',str(k))).lower()]=hk(unicodedata.normalize('NFKC',str(v))).lower()
    rows=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-source-table.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if len(x)<7 or x[6]!='AUTHOR_DIFF': continue
        rows.append(x)
    # 作品単位に集約(slug)
    byslug=defaultdict(lambda:{'title':'','our':set(),'src':set(),'n':0})
    for x in rows:
        s=byslug[x[1]]; s['title']=x[2]; s['our']|=names(x[3]); s['src']|=names(x[5]); s['n']+=1
    real=[]; same=0
    for slug,s in byslug.items():
        our=s['our']; src=s['src']
        # 読み一致(辞書で引けた分)
        oy={yomi.get(n) for n in our if yomi.get(n)}; sy={yomi.get(n) for n in src if yomi.get(n)}
        read_match=bool(oy & sy)
        if subov(our,src) or read_match:
            same+=1
        else:
            real.append([slug,s['title'],';'.join(sorted(our))[:24],';'.join(sorted(src))[:24],s['n']])
    real.sort(key=lambda r:-r[4])
    with open(ROOT/'data'/'seeds'/'author-diff-real.tsv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','our_author','src_author(種1/楽天)','誤ISBN数'])
        for r in real: w.writerow(r)
    print(f'AUTHOR_DIFF 作品単位 {len(byslug)} → (a)表記違い(除外) {same} / (b)真の著者誤り候補 {len(real)}')
    print('-- (b)真の候補 サンプル(誤ISBN多い順) --')
    for r in real[:22]: print(f'  {r[0][:22]:22s}「{r[1][:14]}」 我[{r[2][:16]}] ≠ 真[{r[3][:16]}] ({r[4]})')

if __name__=='__main__': main()
