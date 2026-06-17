#!/usr/bin/env python3
"""
特装版混入 取り直し(outOfStockFlag=1)= 既存(a)(b)で取りこぼした残りを、楽天「在庫切れ込み」で再取得。

残り = 標準枠の isbn が 種1 schema:version=おまけ特装/限定 のまま(=まだ未修正)の巻。
方式(化物語で実証): 作品ごとに **title検索 outOfStockFlag=1** → 特装ISBNを起点(series確証)に
  **同巻の通常版(version語なし)**を確証採用。 通常版主+特装variant(価格・書影込)。

出力: data/seeds/special-edition-fix-redo.yml(採用) + .cache/genre-rakuten/sef-redo-review.tsv(未マッチ)
適用: _special_edition_fix_apply.py --seed data/seeds/special-edition-fix-redo.yml
"""
import json,re,sqlite3,time,subprocess,urllib.request,urllib.parse,urllib.error,sys
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
from urllib.parse import urlparse
REF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(REF); ORIGIN=f'{_o.scheme}://{_o.netloc}'
CACHE=ROOT/'.cache'/'sef-redo-rk'; CACHE.mkdir(parents=True,exist_ok=True)

def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
        return None
    return v
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def vnum(t):
    m=re.search(r'[（(](\d{1,3})[）)]',zen(t));
    if m: return int(m.group(1))
    m=re.search(r'(\d{1,3})\s*巻',zen(t)); return int(m.group(1)) if m else None
def to13(s):
    s=str(s or '').replace('-','').strip(); return s
def norm_t(s):
    s=zen(s); s=re.sub(r'[\s　・:：，,。．\-ー~〜()（）\[\]【】!！?？&＆]','',s); return s.lower()
SP=('特装','限定','フィギュア','ドラマCD','同梱','付き','付','豪華','エキスパンション','BOX','缶バッジ','アクリル','カレンダー','小冊子','特典','初回','特別','DVD','BD','CD','画集')
def is_sp(t): return any(k in t for k in SP)
OMAKE=('特装','限定','フィギュア','ドラマCD','同梱','付き','付','豪華','エキスパンション','BOX','缶バッジ','アクリル','カレンダー','小冊子','特典','初回')
def is_omake(v): return bool(v) and any(k in v for k in OMAKE) and not any(k in v for k in ('文庫','新書','新装版','完全版','愛蔵版'))
def cov(b):
    u=b.get('largeImageUrl') or ''
    if u and 'noimage' not in u: return u.split('?')[0]+'?_ex=200x200'
    i=to13(b.get('isbn'))
    return f'https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{i[-4:]}/{i}.jpg?_ex=200x200' if len(i)==13 else None

def title_search(title):
    cf=CACHE/(re.sub(r'[^\w]','_',title)[:60]+'.json')
    if cf.exists():
        try: return json.loads(cf.read_text(encoding='utf-8'))
        except: pass
    items=[]
    for pg in range(1,6):
        p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'format':'json','formatVersion':'2','title':title,'hits':30,'page':pg,'booksGenreId':'001001','outOfStockFlag':1}
        u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
        req=urllib.request.Request(u,headers={'Referer':REF,'Origin':ORIGIN,'User-Agent':'M/0.1','Accept':'application/json'})
        d=None
        for at in range(4):
            try: d=json.loads(urllib.request.urlopen(req,timeout=25).read()); break
            except urllib.error.HTTPError as e:
                if e.code==429: time.sleep(1.3*(at+1)); continue
                d={'Items':[]}; break
            except Exception: time.sleep(0.4); continue
        its=(d or {}).get('Items') or []
        items+=[{'isbn':to13(b.get('isbn')),'title':b.get('title') or '','price':b.get('itemPrice'),'cover':cov(b)} for b in its]
        if len(its)<30: break
        time.sleep(0.25)
    cf.write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8')
    return items

def main():
    t0=time.time()
    g=json.load(open('.cache/madb/metadata101.json',encoding='utf-8'))['@graph']
    ver={}
    for r in g:
        if r.get('@type')!='class:MangaBook': continue
        i=to13(first(r.get('schema:isbn')))
        if i: ver[i]=(first(r.get('schema:version')) or '').strip()
    print(f'[{time.time()-t0:.0f}s] 種1 version index',flush=True)
    c=sqlite3.connect('.cache/db-v2.sqlite')
    std=set(to13(i) for (i,) in c.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.type='standard' AND v.isbn13 IS NOT NULL"))
    rem={i for i in std if is_omake(ver.get(i,''))}
    Path('.cache/sef-redo-isbns.txt').write_text('\n'.join(rem),encoding='utf-8')
    try:
        out=subprocess.run(['rg','-l','-F','-f','.cache/sef-redo-isbns.txt','data/manga.v2/'],capture_output=True,text=True,timeout=600)
        files=[Path(p) for p in out.stdout.splitlines() if p.strip()]
    except Exception:
        files=list((ROOT/'data'/'manga.v2').glob('*.yml'))
    # 現production標準枠で まだ特装isbnのままの巻 を作品単位で
    works={}
    for fp in files:
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        if not isinstance(d,dict): continue
        vols=[]
        for e in (d.get('editions') or []):
            if e.get('type')!='standard': continue
            for v in (e.get('volumes') or []):
                i=to13(v.get('isbn13'))
                if i in rem: vols.append({'number':v.get('number'),'special_isbn':i,'version':ver.get(i,'')})
        if vols: works[d.get('slug')]={'title':d.get('title'),'vols':vols}
    nv=sum(len(w['vols']) for w in works.values())
    print(f'残り特装混入(未修正): {len(works)}作 / {nv}巻',flush=True)

    corr=[]; review=[]; hi=0; ng=0; n=0
    for slug,w in works.items():
        n+=1
        if n%40==0: print(f'  {n}/{len(works)} (採用 {hi}) [{time.time()-t0:.0f}s]',flush=True)
        items=title_search(w['title'])
        bym={it['isbn']:it for it in items if it['isbn']}
        wcore=norm_t(w['title'])
        for tv in w['vols']:
            si=tv['special_isbn']; vn=tv['number']
            # series確証: 特装ISBNが結果に在る(無ければ題名コアで代替確認)
            sp_item=bym.get(si)
            pool=items if (sp_item or any(wcore[:8] in norm_t(it['title']) for it in items)) else []
            cands=[it for it in pool if it['isbn'] and it['isbn']!=si and not is_sp(it['title']) and vnum(it['title'])==vn and (wcore[:8] in norm_t(it['title']) or norm_t(it['title'])[:8] in wcore)]
            if not cands:
                ng+=1; review.append((w['title'],vn,tv['version'],si,'','none')); continue
            def near(x): return abs(int(si[3:])-int(x['isbn'][3:])) if si[3:].isdigit() and x['isbn'][3:].isdigit() else 9999
            cands.sort(key=lambda x:(near(x), x['price'] or 99999))
            nm=cands[0]
            if not nm.get('cover'):
                review.append((w['title'],vn,tv['version'],si,nm['isbn'],'no-cover')); continue
            corr.append({'special_isbn':si,'normal_isbn':nm['isbn'],'normal_cover':nm['cover'],'normal_date':None,
                         'variant':{'label':tv['version'] or '特装版','isbn13':si,
                                    'cover_url':(sp_item or {}).get('cover'),'price':(sp_item or {}).get('price')}})
            hi+=1
    hdr=("# 特装版混入 取り直し(outOfStockFlag=1)。 在庫切れ含む題名検索で通常版を再取得。 通常版主+特装variant(案B)。\n")
    (ROOT/'data'/'seeds'/'special-edition-fix-redo.yml').write_text(hdr+yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False),encoding='utf-8')
    with (ROOT/'.cache'/'genre-rakuten'/'sef-redo-review.tsv').open('w',encoding='utf-8') as f:
        f.write('title\tvol\tversion\tspecial_isbn\tnormal_isbn\tstatus\n')
        for r in review: f.write('\t'.join(str(x) for x in r)+'\n')
    print(f'\n取り直し: 採用 {hi} / 未マッチ {ng} / no-cover {len(review)-ng}',flush=True)
    print('seed → data/seeds/special-edition-fix-redo.yml',flush=True)

if __name__=='__main__': main()
