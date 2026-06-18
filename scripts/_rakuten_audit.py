#!/usr/bin/env python3
"""
楽天種オラクル監査(読み取りのみ・本番変更なし)。
DB全巻のISBNを楽天種(ISBN→正題/巻/出版社/画像)で突合し4類型をflag:
 T1 版混在(巻数間違い): 1版内に楽天出版社が2社以上(北斗=集英社/新潮社)
 T2 烈火型: 我々ISBNの楽天記録がnoimage かつ シリーズ/巻は一致(=正しい巻だが無画像の別版)→正版を引き直す候補
 T3 未知型(別物・サイレント): 我々ISBNの楽天シリーズ名が我々作品名と不一致(画像は出るが中身が別作)
 T4 巻数違い: 我々巻番号 ≠ 楽天題の巻番号
出力: data/seeds/audit-T1..T4.tsv + 集計。
"""
import sys,re,json,csv,time,unicodedata,difflib
from pathlib import Path
from collections import Counter,defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
SEED=ROOT/'.cache'/'rakuten-isbn.jsonl'

EDIT_TOKENS=['特装版','限定版','完全版','新装版','愛蔵版','文庫版','文庫','ワイド版','ワイド','コレクション',
 'premium','プレミアム','大全集','総集編','合本','カラー版','フルカラー','オールカラー','復刻版','新装再編版',
 '初回限定版','初回版','特別版','豪華版','box','セット','分冊版','電子限定','コミック','comic']
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def split_reading(s):
    if not s: return ''
    return re.split(r'\s*[∥｜]\s*',str(s))[0].strip()
def norm_series(s):
    s=split_reading(s); s=zen(s); s=unicodedata.normalize('NFKC',s)
    s=re.sub(r'[（(〈［\[【].*?[）)〉］\]】]','',s)   # 括弧(巻/版名)除去
    low=s.lower()
    for t in EDIT_TOKENS: low=low.replace(t,'')
    low=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',low)
    low=re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),low)  # ひら→カタ
    return low
def parse_vol(title):
    t=zen(str(title)).strip()
    for pat in (r'[（(](\d{1,4})[）)]', r'第(\d{1,4})\s*巻', r'(\d{1,4})\s*巻', r'〈(\d{1,4})〉'):
        m=re.search(pat,t)
        if m: return int(m.group(1))
    m=re.search(r'[\s　](\d{1,3})\s*$', t)   # 題名+番号(先頭スペース必須=数字のみ題名は弾く)
    return int(m.group(1)) if m else None
def lcs_len(a,b):
    if not a or not b: return 0
    prev=[0]*(len(b)+1); best=0
    for i in range(1,len(a)+1):
        cur=[0]*(len(b)+1)
        for j in range(1,len(b)+1):
            if a[i-1]==b[j-1]:
                cur[j]=prev[j-1]+1
                if cur[j]>best: best=cur[j]
        prev=cur
    return best
def same_series(a,b):
    if not a or not b: return True
    if a in b or b in a: return True
    l=lcs_len(a,b)
    if l>=5 and l>=0.45*min(len(a),len(b)): return True
    if len(a)>=3 and difflib.SequenceMatcher(None,a,b).ratio()>=0.62: return True
    return False
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    t0=time.time()
    print('楽天種オラクル構築中...',flush=True)
    oracle={}
    for line in SEED.open(encoding='utf-8'):
        try: r=json.loads(line)
        except: continue
        it=r.get('item') or {}
        ib=to13(r.get('isbn') or it.get('isbn'))
        if not ib: continue
        title=it.get('title') or ''
        url=it.get('largeImageUrl') or it.get('mediumImageUrl') or ''
        oracle[ib]={'t':title,'pub':split_reading(it.get('publisherName') or ''),
                    'vol':parse_vol(title),'cov':bool(url and 'noimage' not in url)}
    print(f'oracle: {len(oracle):,} ISBN [{time.time()-t0:.0f}s]',flush=True)

    T1=[];T2=[];T3=[];T4=[]
    notfound=0; checked=0
    M=ROOT/'data'/'manga.v2'
    for i,fp in enumerate(M.glob('*.yml')):
        if i%15000==0 and i: print(f'  scan ...{i} [{time.time()-t0:.0f}s]',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        slug=d.get('slug'); wtitle=d.get('title') or ''; wcore=norm_series(wtitle)
        for e in (d.get('editions') or []):
            etype=e.get('type'); pubset=Counter(); bypub=defaultdict(list)
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                if not ib: continue
                o=oracle.get(ib)
                if not o: notfound+=1; continue
                checked+=1
                ovn=v.get('number'); ovn=int(ovn) if isinstance(ovn,(int,float)) else None
                rcore=norm_series(o['t'])
                # シリーズ一致判定(共通部分文字列ベース=副題違い/部分一致に強い)
                ser_ok = bool(rcore) and same_series(wcore,rcore)
                if not ser_ok and rcore and len(wcore)>=3:
                    T3.append([slug,wtitle,etype,ovn,ib,o['t'][:40],rcore[:20]])
                    continue   # 別物なら巻/版判定はスキップ
                # 巻番号一致
                if ovn is not None and o['vol'] is not None and ovn!=o['vol']:
                    T4.append([slug,wtitle,etype,ovn,ib,o['vol'],o['t'][:40]])
                # 烈火型(画像なし・正しい巻)
                if not o['cov']:
                    T2.append([slug,wtitle,etype,ovn,ib,o['t'][:40]])
                # 版混在(出版社集計)
                if o['pub']: pubset[o['pub']]+=1; bypub[o['pub']].append(ovn)
            if len(pubset)>=2:
                maj=pubset.most_common(1)[0][0]; minors=[p for p in pubset if p!=maj]
                mv=sorted(x for p in minors for x in bypub[p] if x is not None)[:20]
                T1.append([slug,wtitle,etype,' | '.join(f'{p}:{pubset[p]}' for p,_ in pubset.most_common()),maj,str(mv)])
    # 出力
    out={'T1-pubmix':(T1,['slug','title','edition','publishers','majority','minority_vols']),
         'T2-rekka':(T2,['slug','title','edition','vol','isbn','rakuten_title']),
         'T3-wrongproduct':(T3,['slug','title','edition','vol','isbn','rakuten_title','rakuten_core']),
         'T4-volmismatch':(T4,['slug','title','edition','our_vol','isbn','rakuten_vol','rakuten_title'])}
    for name,(rows,hdr) in out.items():
        p=ROOT/'data'/'seeds'/f'audit-{name}.tsv'
        with open(p,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f,delimiter='\t'); w.writerow(hdr)
            for r in rows: w.writerow(r)
    print(f'\n=== 楽天種監査(照合{checked:,}巻 / 種に無いISBN{notfound:,}) ===')
    print(f' T1 版混在(版内2社+)   : {len(T1):,} 版')
    print(f' T2 烈火型(noimage正巻): {len(T2):,} 巻')
    print(f' T3 未知型(別物/サイレント): {len(T3):,} 巻 ★最重要')
    print(f' T4 巻数違い            : {len(T4):,} 巻')
    print('\n-- T3 サンプル(画像出てるが別作の疑い)--')
    for r in T3[:12]: print(f'  {str(r[1])[:18]:18s} vol{r[3]} {r[4]} → 楽天「{r[5]}」')
    print('-- T4 サンプル --')
    for r in T4[:8]: print(f'  {str(r[1])[:18]:18s} 我々{r[3]}巻 ≠ 楽天{r[5]}巻 「{r[6]}」')

if __name__=='__main__': main()
