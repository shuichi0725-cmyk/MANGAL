#!/usr/bin/env python3
"""
監査の修正用データ収集(読み取りのみ・本番不変)。
楽天種から ②索引(シリーズ正規化, 巻 → ISBN群[画像有優先]) を作り、
DB全巻に「種が示す正解候補ISBN/画像」を付ける。 各類型が種だけで直せるか/外部(API/NDL)要かを切り分け。
出力:
 data/seeds/resolve-master.tsv  … DB全巻 × {現ISBN/画像, 種提案ISBN/画像, 一致種別}
 data/seeds/resolve-summary.txt … 類型別 解決可否の集計
 data/seeds/needs-external.tsv  … 種で解決できない flagged 巻(API/NDL対象)
"""
import sys,json,csv,time,unicodedata,re,difflib
from pathlib import Path
from collections import defaultdict,Counter
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
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    t0=time.time()
    print('楽天種 → ②索引 構築...',flush=True)
    oracle={}; idx=defaultdict(lambda: defaultdict(list))
    for line in SEED.open(encoding='utf-8'):
        try: r=json.loads(line)
        except: continue
        it=r.get('item') or {}
        ib=to13(r.get('isbn') or it.get('isbn'))
        if not ib: continue
        title=it.get('title') or ''
        url=it.get('largeImageUrl') or it.get('mediumImageUrl') or ''
        cov=bool(url and 'noimage' not in url)
        ser=norm_series(title); vol=parse_vol(title); pub=split_reading(it.get('publisherName') or '')
        oracle[ib]={'t':title,'ser':ser,'vol':vol,'pub':pub,'cov':cov,
                    'cover':(url.split('?')[0]+'?_ex=200x200') if cov else None}
        if ser and vol is not None:
            idx[ser][vol].append({'isbn':ib,'cov':cov,'pub':pub,
                                  'cover':(url.split('?')[0]+'?_ex=200x200') if cov else None})
    print(f'oracle {len(oracle):,} / 索引シリーズ {len(idx):,} [{time.time()-t0:.0f}s]',flush=True)

    # DB: isbn→slugs(共有検出), 全巻解決
    M=ROOT/'data'/'manga.v2'
    isbn_slugs=defaultdict(set)
    rows=[]   # 解決master
    for i,fp in enumerate(M.glob('*.yml')):
        if i%15000==0 and i: print(f'  scan ...{i} [{time.time()-t0:.0f}s]',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        slug=d.get('slug'); wtitle=d.get('title') or ''; wser=norm_series(wtitle)
        for e in (d.get('editions') or []):
            et=e.get('type')
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                ovn=v.get('number'); ovn=int(ovn) if isinstance(ovn,(int,float)) else None
                ccov=bool(v.get('cover_url'))
                if ib: isbn_slugs[ib].add(slug)
                # 種提案: 我々シリーズ+巻 に一致する索引entry(画像有優先・同シリーズ)
                prop=None; mt='none'
                if wser and ovn is not None and wser in idx and ovn in idx[wser]:
                    cands=idx[wser][ovn]
                    covd=[c for c in cands if c['cov']]
                    pick=(covd or cands)[0]
                    prop=pick; mt='seed-cover' if pick['cov'] else 'seed-nocover'
                rows.append([slug,wtitle,et,ovn,ib,'Y' if ccov else 'N',
                             prop['isbn'] if prop else '', 'Y' if (prop and prop['cov']) else 'N', mt])
    # 共有ISBN(複数slug)注記
    shared={ib for ib,ss in isbn_slugs.items() if len(ss)>=2}
    for r in rows: r.append(len(isbn_slugs.get(r[4],()))) if r[4] else r.append(0)

    out=ROOT/'data'/'seeds'/'resolve-master.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['slug','title','edition','vol','cur_isbn','cur_cover','seed_isbn','seed_cover','match','isbn_used_by_works'])
        for r in rows: w.writerow(r)

    # 集計
    no_cover=[r for r in rows if r[5]=='N' and r[4]]
    nc_fixable=[r for r in no_cover if r[8]=='seed-cover' and r[6]!=r[4]]      # T2烈火: 種に画像ありの別ISBN
    nc_sameisbn_cover=[r for r in no_cover if r[8]=='seed-cover' and r[6]==r[4]] # 同ISBNが種では画像あり(.gif等で取り逃し)
    shared_rows=[r for r in rows if r[4] and r[-1]>=2]
    needs_ext=[r for r in no_cover if r[8]=='none']                            # 種で解決不能=API/NDL
    with open(ROOT/'data'/'seeds'/'needs-external.tsv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','edition','vol','cur_isbn'])
        for r in needs_ext: w.writerow(r[:5])
    summ=[]
    summ.append(f'DB巻(ISBN有)照合: {sum(1 for r in rows if r[4]):,}')
    summ.append(f'無画像巻: {len(no_cover):,}')
    summ.append(f'  ├ 同ISBNが種では画像あり(.gif等取り逃し=即修正可): {len(nc_sameisbn_cover):,}')
    summ.append(f'  ├ 烈火型(別ISBNに画像あり=種で正版に差替可): {len(nc_fixable):,}')
    summ.append(f'  └ 種で解決不能(API/NDL要): {len(needs_ext):,}')
    summ.append(f'同一ISBN複数作品(T3核心) 行: {len(shared_rows):,} / ユニークISBN {len(shared):,}')
    txt='\n'.join(summ)
    (ROOT/'data'/'seeds'/'resolve-summary.txt').write_text(txt,encoding='utf-8')
    print('\n=== 解決データ集計 ==='); print(txt)
    print(f'\n→ resolve-master.tsv / needs-external.tsv / resolve-summary.txt')

if __name__=='__main__': main()
