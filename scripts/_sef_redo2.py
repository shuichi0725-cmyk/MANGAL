#!/usr/bin/env python3
"""
未マッチ201の取り直し(第3パス)= 特装ISBNを起点に楽天の日本語 seriesName を取得し、
それで検索(outOfStockFlag=1)して同巻の通常版を確証採用。
(redoの取りこぼし主因 = DB題が英語/ローマ字で楽天日本語題に当たらなかった、を是正)

入力: data/seeds/special-edition-fix-redo-review.tsv の status=none
出力: data/seeds/special-edition-fix-redo2.yml + .cache/genre-rakuten/sef-redo2-review.tsv
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
CACHE=ROOT/'.cache'/'sef-redo2-rk'; CACHE.mkdir(parents=True,exist_ok=True)

def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def vnum(t):
    t=zen(t)
    m=re.search(r'[（(](\d{1,3})[）)]',t)
    if m: return int(m.group(1))
    m=re.search(r'(\d{1,3})\s*巻',t)
    if m: return int(m.group(1))
    # ★「題名␣N」形式(半角/全角スペース+末尾数字)。 楽天は通常版をこの形式で返すことが多い
    m=re.search(r'[\s　](\d{1,3})\s*$',t)
    if m: return int(m.group(1))
    return None
def to13(s):
    s=str(s or '').replace('-','').strip(); return s
def norm_t(s):
    s=zen(s); s=re.sub(r'[\s　・:：，,。．\-ー~〜()（）\[\]【】!！?？&＆]','',s); return s.lower()
SP=('特装','限定','フィギュア','ドラマCD','同梱','付き','付','豪華','エキスパンション','BOX','缶バッジ','アクリル','カレンダー','小冊子','特典','初回','特別','DVD','BD','CD','画集','ぬいぐるみ','スタンド')
def is_sp(t): return any(k in t for k in SP)
def cov(b):
    u=b.get('largeImageUrl') or ''
    if u and 'noimage' not in u: return u.split('?')[0]+'?_ex=200x200'
    i=to13(b.get('isbn'))
    return f'https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{i[-4:]}/{i}.jpg?_ex=200x200' if len(i)==13 else None

def api(**kw):
    time.sleep(1.0)  # ★楽天 ~1req/sec 厳守(速いと429で空振り→取りこぼし。 余分0.1は件数次第で~10%無駄)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'format':'json','formatVersion':'2','hits':30,'booksGenreId':'001001'}; p.update(kw)
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    req=urllib.request.Request(u,headers={'Referer':REF,'Origin':ORIGIN,'User-Agent':'M/0.1','Accept':'application/json'})
    for at in range(4):
        try: return json.loads(urllib.request.urlopen(req,timeout=25).read())
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(1.3*(at+1)); continue
            return {'Items':[]}
        except Exception: time.sleep(0.4)
    return {'Items':[]}

def by_isbn(isbn):
    cf=CACHE/f'isbn_{isbn}.json'
    if cf.exists():
        try: return json.loads(cf.read_text(encoding='utf-8'))
        except: pass
    d=api(isbn=isbn,outOfStockFlag=1)
    its=d.get('Items') or []
    r=its[0] if its else {}
    cf.write_text(json.dumps(r,ensure_ascii=False),encoding='utf-8'); return r

def series_items(name):
    cf=CACHE/('s_'+re.sub(r'[^\w]','_',name)[:50]+'.json')
    if cf.exists():
        try: return json.loads(cf.read_text(encoding='utf-8'))
        except: pass
    items=[]
    for pg in range(1,14):
        d=api(title=name,page=pg,outOfStockFlag=1)
        its=d.get('Items') or []
        items+=[{'isbn':to13(b.get('isbn')),'title':b.get('title') or '','price':b.get('itemPrice'),'cover':cov(b)} for b in its]
        if len(its)<30: break
        time.sleep(0.35)
    cf.write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8'); return items

def main():
    todo=[]
    for ln in open(ROOT/'data'/'seeds'/'special-edition-fix-redo-review.tsv',encoding='utf-8'):
        p=ln.rstrip('\n').split('\t')
        if len(p)<6 or p[0]=='title' or p[5]!='none': continue
        todo.append({'title':p[0],'vol':int(p[1]) if p[1].isdigit() else None,'version':p[2],'special_isbn':p[3]})
    print(f'未マッチ {len(todo)} を seriesName経由で再取得',flush=True)
    corr=[]; review=[]; hi=0; t0=time.time()
    for n,tv in enumerate(todo,1):
        if n%30==0: print(f'  {n}/{len(todo)} (採用{hi}) [{time.time()-t0:.0f}s]',flush=True)
        si=tv['special_isbn']; vn=tv['vol']
        sp=by_isbn(si)
        sp_cov=cov(sp); sp_price=sp.get('itemPrice')
        # ★作品名 = 特装タイトルの「巻番号より前」(seriesName=レーベル名なので使わない)
        rt=zen(sp.get('title') or '')
        # 括弧書き(【特装版】等)を先に除去 → 巻番号で切る → 残った特装語も除去
        rt2=re.sub(r'【[^】]*】|〔[^〕]*〕|\[[^\]]*\]','',rt)
        mm=re.search(r'[（(]\d{1,3}[）)]|\s\d{1,3}(\s|$)|\d{1,3}\s*巻', rt2)
        sname=(rt2[:mm.start()].strip() if mm else rt2.strip())
        for k in ('特装版','限定版','特別版','初回限定','完全生産限定','豪華版','特装','限定'):
            sname=sname.replace(k,'')
        sname=sname.strip(' 　・　')
        if not sname:
            review.append((tv['title'],vn,tv['version'],si,'','no-title')); continue
        items=series_items(sname)
        score=norm_t(sname)
        cands=[it for it in items if it['isbn'] and it['isbn']!=si and not is_sp(it['title']) and vnum(it['title'])==vn and (score[:6] in norm_t(it['title']) or norm_t(it['title'])[:6] in score)]
        if not cands:
            review.append((tv['title'],vn,tv['version'],si,'',f'series={sname[:16]}/none')); continue
        def near(x): return abs(int(si[3:])-int(x['isbn'][3:])) if si[3:].isdigit() and x['isbn'][3:].isdigit() else 9999
        cands.sort(key=lambda x:(near(x), x['price'] or 99999))
        nm=cands[0]
        if not nm.get('cover'):
            review.append((tv['title'],vn,tv['version'],si,nm['isbn'],'no-cover')); continue
        corr.append({'special_isbn':si,'normal_isbn':nm['isbn'],'normal_cover':nm['cover'],'normal_date':None,
                     'variant':{'label':tv['version'] or '特装版','isbn13':si,'cover_url':sp_cov,'price':sp_price}})
        hi+=1
    (ROOT/'data'/'seeds'/'special-edition-fix-redo2.yml').write_text(
        "# 未マッチ201の取り直し(seriesName経由・outOfStockFlag=1)。 通常版主+特装variant(案B)。\n"+
        yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False),encoding='utf-8')
    with (ROOT/'.cache'/'genre-rakuten'/'sef-redo2-review.tsv').open('w',encoding='utf-8') as f:
        f.write('title\tvol\tversion\tspecial_isbn\tnormal_isbn\tstatus\n')
        for r in review: f.write('\t'.join(str(x) for x in r)+'\n')
    print(f'\n第3パス: 採用 {hi} / なお未マッチ {len(review)}',flush=True)

if __name__=='__main__': main()
