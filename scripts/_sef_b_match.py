#!/usr/bin/env python3
"""
(b)化物語型: 楽天で通常版ISBNを特定(慎重・確証付き)。
著者検索→items→(巻番号一致 ∧ 題名コア一致 ∧ 特装語なし)で通常版候補→confidence判定。
high=採用seed / med・なし=レビューTSV。 だろう運転禁止([[merge_needs_external_proof]])。

出力: data/seeds/special-edition-fix-b.yml(high) + .cache/genre-rakuten/sef-b-review.tsv
"""
import json,re,time,urllib.request,urllib.parse,urllib.error,sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
from urllib.parse import urlparse
REF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(REF); ORIGIN=f'{_o.scheme}://{_o.netloc}'
CACHE=ROOT/'.cache'/'sef-b-rakuten'; CACHE.mkdir(parents=True,exist_ok=True)
SPECIAL=('特装','限定','フィギュア','ドラマCD','同梱','付き','付','豪華','エキスパンション','BOX','缶バッジ','アクリル','カレンダー','小冊子','特典','初回','特別','DVD','BD','CD')

def zen2han(s):
    return s.translate(str.maketrans('０１２３４５６７８９','0123456789'))
def norm(s):
    s=zen2han(str(s or '')); s=re.sub(r'[\s　・:：，,。．\-ー~〜()（）\[\]【】]','',s); return s.lower()
def parse_vol(title):
    t=zen2han(title)
    m=re.search(r'[（(](\d{1,3})[）)]',t)
    if m: return int(m.group(1))
    m=re.search(r'(\d{1,3})\s*巻',t)
    if m: return int(m.group(1))
    return None
def is_special(t):
    return any(k in t for k in SPECIAL)
def construct_cover(isbn):
    last4=isbn[-4:]
    for suf in ('.jpg','_1_2.jpg','_1_4.jpg'):
        u=f'https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{last4}/{isbn}{suf}?_ex=200x200'
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=10)
            d=r.read()
            if 'image' in r.headers.get('Content-Type','') and len(d)>2000: return u
        except Exception: pass
    return None

def author_items(author):
    cf=CACHE/(re.sub(r'[^\w]','_',author)+'.json')
    if cf.exists():
        try: return json.loads(cf.read_text(encoding='utf-8'))
        except: pass
    items=[]
    for pg in (1,2,3):
        p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'format':'json','formatVersion':'2','author':author,'hits':30,'page':pg,'booksGenreId':'001001'}
        u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
        req=urllib.request.Request(u,headers={'Referer':REF,'Origin':ORIGIN,'User-Agent':'MANGAL-DataFetch/0.1','Accept':'application/json'})
        ok=False
        for at in range(4):
            try:
                d=json.loads(urllib.request.urlopen(req,timeout=25).read()); ok=True; break
            except urllib.error.HTTPError as e:
                if e.code==429: time.sleep(1.2*(at+1)); continue
                break
            except Exception: time.sleep(0.4); continue
        if not ok: break
        its=d.get('Items') or []
        for b in its:
            items.append({'isbn':str(b.get('isbn') or '').replace('-',''),'title':b.get('title') or '','price':b.get('itemPrice'),'pub':b.get('publisherName') or ''})
        if len(its)<30: break
        time.sleep(0.25)
    cf.write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8')
    return items

def main():
    works=json.loads((ROOT/'.cache'/'genre-rakuten'/'sef-b-targets.json').read_text(encoding='utf-8'))
    corr=[]; review=[]; hi=md=no=0
    t0=time.time(); n=0
    for slug,w in works.items():
        n+=1
        if n%40==0: print(f'  {n}/{len(works)} (high {hi}) [{time.time()-t0:.0f}s]',flush=True)
        title=w['title']; wcore=norm(title)
        items=[]
        for au in w['authors'][:2]:
            items+=author_items(au)
        # index normal items by volume
        for tv in w['vols']:
            vn=tv['number']; sp_isbn=tv['special_isbn']
            cands=[]
            for it in items:
                if not it['isbn'] or it['isbn']==sp_isbn: continue
                if is_special(it['title']): continue
                iv=parse_vol(it['title'])
                if iv!=vn: continue
                ic=norm(it['title'])
                # 題名コア一致: 作品題が item題に含まれる or 双方の頭一致
                if not (wcore and (wcore[:8] in ic or ic[:8] in wcore)): continue
                near=abs(int(sp_isbn[3:])-int(it['isbn'][3:]))<200 if it['isbn'].isdigit() and sp_isbn.isdigit() else False
                cands.append((it,near))
            if not cands:
                no+=1; review.append((title,vn,tv['version'],sp_isbn,'','none',''))
                continue
            # 確証: 単一 or ISBN近接 を優先
            cands.sort(key=lambda x:(0 if x[1] else 1, x[0]['price'] or 99999))
            it,near=cands[0]
            conf='high' if (near or len([c for c in cands if c])==1) else 'med'
            cover=construct_cover(it['isbn'])
            row={'special_isbn':sp_isbn,'normal_isbn':it['isbn'],'normal_cover':cover,'normal_date':None,
                 'variant':{'label':tv['version'],'isbn13':sp_isbn,'cover_url':construct_cover(sp_isbn),'price':None},
                 'slug':slug,'vol':vn,'conf':conf,'normal_title':it['title'],'normal_price':it['price']}
            if conf=='high' and cover:
                corr.append({k:row[k] for k in ('special_isbn','normal_isbn','normal_cover','normal_date','variant')})
                hi+=1
            else:
                md+=1
            review.append((title,vn,tv['version'],sp_isbn,it['isbn'],conf+('' if cover else '/no-cover'),it['title'][:30]))
    # write
    hdr=("# (b)化物語型 修正候補(楽天で通常版ISBN特定・high確証のみ)。 通常版主+特装variant(案B)。\n"
         "# 生成 _sef_b_match.py。 med/none は sef-b-review.tsv で要レビュー。\n")
    (ROOT/'data'/'seeds'/'special-edition-fix-b.yml').write_text(hdr+yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False),encoding='utf-8')
    with (ROOT/'.cache'/'genre-rakuten'/'sef-b-review.tsv').open('w',encoding='utf-8') as f:
        f.write('title\tvol\tversion\tspecial_isbn\tnormal_isbn\tconf\tnormal_title\n')
        for r in review: f.write('\t'.join(str(x) for x in r)+'\n')
    print(f'\n(b)結果: high採用 {hi} / med {md} / 通常版見つからず {no}',flush=True)
    print(f'high seed → data/seeds/special-edition-fix-b.yml / review → .cache/genre-rakuten/sef-b-review.tsv',flush=True)

if __name__=='__main__': main()
