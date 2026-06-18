#!/usr/bin/env python3
"""
T3核心: 同一ISBNが複数作品に付いている(1,770ISBN)の所有判定 + 誤側の正ISBN提案。
楽天種メタデータのみ(画像不使用)。
- 共有ISBNの楽天シリーズ名に一致する作品=正所有者。 不一致の作品=誤付与。
- 誤付与作品の正ISBN = ②索引(その作品シリーズ+巻)から提案。 種に無ければ NDL対象(metaのみ)。
出力: data/seeds/t3-ownership.tsv + 集計。 本番不変。
"""
import sys,json,csv,time,unicodedata,re,difflib
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
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
    s=re.sub(r'[（(〈［\[【].*?[）)〉］\]】]','',s)
    low=s.lower()
    for t in EDIT_TOKENS: low=low.replace(t,'')
    low=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',low)
    low=re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),low)
    return low
def parse_vol(title):
    t=zen(str(title)).strip()
    for pat in (r'[（(](\d{1,4})[）)]', r'第(\d{1,4})\s*巻', r'(\d{1,4})\s*巻', r'〈(\d{1,4})〉'):
        m=re.search(pat,t)
        if m: return int(m.group(1))
    m=re.search(r'[\s　](\d{1,3})\s*$', t)
    return int(m.group(1)) if m else None
def lcs_len(a,b):
    if not a or not b: return 0
    prev=[0]*(len(b)+1); best=0
    for i in range(1,len(a)+1):
        cur=[0]*(len(b)+1)
        for j in range(1,len(b)+1):
            if a[i-1]==b[j-1]:
                cur[j]=prev[j-1]+1; best=max(best,cur[j])
        prev=cur
    return best
def same_series(a,b):
    if not a or not b: return False
    if a in b or b in a: return True
    l=lcs_len(a,b)
    if l>=5 and l>=0.45*min(len(a),len(b)): return True
    if len(a)>=3 and difflib.SequenceMatcher(None,a,b).ratio()>=0.62: return True
    return False
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    t0=time.time()
    print('楽天種 oracle+②索引...',flush=True)
    oracle={}; idx=defaultdict(lambda: defaultdict(list))
    for line in SEED.open(encoding='utf-8'):
        try: r=json.loads(line)
        except: continue
        it=r.get('item') or {}; ib=to13(r.get('isbn') or it.get('isbn'))
        if not ib: continue
        title=it.get('title') or ''; url=it.get('largeImageUrl') or ''
        cov=bool(url and 'noimage' not in url)
        ser=norm_series(title); vol=parse_vol(title)
        oracle[ib]={'t':title,'ser':ser,'vol':vol,'cov':cov}
        if ser and vol is not None: idx[ser][vol].append({'isbn':ib,'cov':cov})
    print(f'oracle {len(oracle):,} [{time.time()-t0:.0f}s]',flush=True)

    # resolve-master から 共有ISBN(>=2作)と (slug,title,vol,cur_isbn) を取得
    isbn_rows=defaultdict(list)
    with open(ROOT/'data'/'seeds'/'resolve-master.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            # slug,title,edition,vol,cur_isbn,cur_cover,seed_isbn,seed_cover,match,isbn_used_by_works
            if len(x)<10: continue
            try: used=int(x[9])
            except: used=0
            if x[4] and used>=2: isbn_rows[x[4]].append({'slug':x[0],'title':x[1],'vol':x[3]})
    print(f'共有ISBN {len(isbn_rows):,}',flush=True)

    out=[]; owner_clear=0; need_ndl=0; seed_fix=0; ambiguous=0
    for ib,rows in isbn_rows.items():
        o=oracle.get(ib)
        rk_ser=o['ser'] if o else ''
        rk_title=o['t'] if o else ''
        owners=[]; wrong=[]
        for w in rows:
            wser=norm_series(w['title'])
            (owners if (rk_ser and same_series(wser,rk_ser)) else wrong).append(w)
        # 誤側の正ISBN提案
        for w in wrong:
            wser=norm_series(w['title'])
            try: wv=int(w['vol'])
            except: wv=None
            prop=''; how='NDL要(meta)'
            if wser in idx and wv is not None and wv in idx[wser]:
                cands=idx[wser][wv]
                # 共有ISBNでない別の候補を優先
                alt=[c for c in cands if c['isbn']!=ib] or cands
                covd=[c for c in alt if c['cov']]
                pick=(covd or alt)[0]; prop=pick['isbn']; how='seed' ; seed_fix+=1
            else:
                need_ndl+=1
            out.append([ib,rk_title[:30],len(owners),
                        (owners[0]['slug'] if owners else '(所有者不明)'),
                        w['slug'],w['vol'],prop,how])
        if owners: owner_clear+=1
        else: ambiguous+=1
    out.sort(key=lambda z:(z[7]!='seed', z[0]))
    p=ROOT/'data'/'seeds'/'t3-ownership.tsv'
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['shared_isbn','rakuten_title','n_owners','owner_slug','wrong_slug','wrong_vol','proposed_isbn','how'])
        for r in out: w.writerow(r)
    print(f'\n=== T3 所有判定 ===')
    print(f'共有ISBN: {len(isbn_rows):,}(所有者確定 {owner_clear:,} / 所有者不明 {ambiguous:,})')
    print(f'誤付与の是正対象(行): {len(out):,}')
    print(f'  ├ 種で正ISBN提案可: {seed_fix:,}')
    print(f'  └ NDL(メタ)要      : {need_ndl:,}')
    print(f'→ {p}')
    print('-- サンプル --')
    for r in out[:12]: print(f'  ISBN{r[0]} 楽天「{r[1][:18]}」 所有={r[3][:16]} 誤={r[4][:16]} vol{r[5]} →提案{r[6]}({r[7]})')

if __name__=='__main__': main()
