#!/usr/bin/env python3
"""
残り117の仕上げ: NDLで通常版ISBNを取得 → 楽天はISBNで書影/価格。
NDL SRU: recordSchema=dcndl, CQL `title=<series> AND ndc=726`(漫画), identifier から 97[89]\\d{10} 抽出。
(タイトル解析でなく構造フィールド=上/下・同梱物名・副題に強い)

入力: data/seeds/special-edition-fix-redo2-review.tsv の status!=採用(none/no-title等)
出力: data/seeds/special-edition-fix-ndl.yml + .cache/genre-rakuten/sef-ndl-review.tsv
"""
import json,re,time,urllib.request,urllib.parse,sys,unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
NDL="https://ndlsearch.ndl.go.jp/api/sru"
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
from urllib.parse import urlparse
RREF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(RREF); RORG=f'{_o.scheme}://{_o.netloc}'
NCACHE=ROOT/'.cache'/'sef-ndl'; NCACHE.mkdir(parents=True,exist_ok=True)

def lnm(t): return t.split('}')[-1]
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def norm_t(s):
    s=zen(s); s=unicodedata.normalize('NFKC',s)
    return re.sub(r'[\s　・:：，,。．\-ー~〜()（）\[\]【】!！?？&＆]','',s).lower()
def to13(s):
    s=str(s or '').replace('-','').strip(); return s
SP=('特装','限定','フィギュア','ドラマCD','同梱','付き','付','豪華','エキスパンション','BOX','缶バッジ','アクリル','カレンダー','小冊子','特典','初回','特別','DVD','BD','CD','画集','ぬいぐるみ','スタンド','セット')
def is_sp(t): return any(k in t for k in SP)

def ndl_req(q):
    url=NDL+'?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'500','query':q})
    for at in range(4):
        try: return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MANGAL/0.1','Accept':'application/xml'}),timeout=40).read()
        except Exception:
            if at<3: time.sleep(3+at*3); continue
            return b''
def ndl_series(name):
    cf=NCACHE/(re.sub(r'[^\w]','_',name)[:50]+'.json')
    if cf.exists():
        try: return json.loads(cf.read_text(encoding='utf-8'))
        except: pass
    time.sleep(1.0)
    b=ndl_req(f'title={name} AND ndc=726')
    out=[]
    if b:
        try: root=ET.fromstring(b)
        except: root=None
        if root is not None:
            for rd in root.iter():
                if lnm(rd.tag)!='recordData': continue
                kids=list(rd)
                it=rd.iter() if kids else (ET.fromstring(rd.text).iter() if rd.text and '<' in rd.text else [])
                title=None; isbn=None
                for el in it:
                    k=lnm(el.tag); t=(el.text or '').strip()
                    if not t: continue
                    if k=='title' and not title: title=t
                    if k=='identifier' and not isbn:
                        m=re.search(r'97[89]\d{10}',t.replace('-',''))
                        if m: isbn=m.group()
                if title and isbn: out.append({'title':title,'isbn':isbn})
    cf.write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
    return out

def rk_cover(isbn):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'format':'json','formatVersion':'2','isbn':isbn,'hits':1,'outOfStockFlag':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read())
        its=d.get('Items') or []
        if its:
            b=its[0]; url=(b.get('largeImageUrl') or '')
            if url and 'noimage' not in url: return url.split('?')[0]+'?_ex=200x200', b.get('itemPrice')
    except Exception: pass
    # fallback: construct
    return f'https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{isbn[-4:]}/{isbn}.jpg?_ex=200x200', None

def main():
    targets=[]
    for ln in open(ROOT/'data'/'seeds'/'special-edition-fix-redo2-review.tsv',encoding='utf-8'):
        p=ln.rstrip('\n').split('\t')
        if len(p)<6 or p[0]=='title': continue
        targets.append({'title':p[0],'vol':int(p[1]) if p[1].isdigit() else None,'version':p[2],'special_isbn':p[3]})
    bytitle=defaultdict(list)
    for t in targets: bytitle[t['title']].append(t)
    print(f'NDL仕上げ: {len(targets)}巻 / {len(bytitle)}作品',flush=True)
    found=[]; review=[]; t0=time.time(); n=0
    for title,tvs in bytitle.items():
        n+=1
        if n%20==0: print(f'  {n}/{len(bytitle)} (found {len(found)}) [{time.time()-t0:.0f}s]',flush=True)
        recs=ndl_series(title)
        wcore=norm_t(title)
        for tv in tvs:
            vn=tv['vol']; si=tv['special_isbn']
            vnpat=re.compile(r'(?<![0-9])'+str(vn)+r'(?![0-9])') if vn is not None else None
            cand=None
            for r in recs:
                rt=zen(r['title']); rc=norm_t(r['title'])
                if to13(r['isbn'])==si: continue
                if is_sp(r['title']): continue
                if not (wcore[:5] in rc or rc[:5] in wcore): continue
                vol_ok = (vnpat and vnpat.search(rt)) or (vn==1 and ('上' in rt)) or (vn==2 and ('下' in rt))
                if vol_ok: cand=r; break
            if cand:
                found.append({**tv,'normal_isbn':to13(cand['isbn']),'ndl_title':cand['title']})
            else:
                review.append((title,vn,tv['version'],si,'ndl-none'))
    print(f'NDLで通常版ISBN取得: {len(found)} / 取れず {len(review)}',flush=True)
    # 楽天で書影
    corr=[]
    for i,f in enumerate(found,1):
        if i%20==0: print(f'  cover {i}/{len(found)} [{time.time()-t0:.0f}s]',flush=True)
        cov,price=rk_cover(f['normal_isbn'])
        scov,_=rk_cover(f['special_isbn'])
        corr.append({'special_isbn':f['special_isbn'],'normal_isbn':f['normal_isbn'],'normal_cover':cov,'normal_date':None,
                     'variant':{'label':f['version'] or '特装版','isbn13':f['special_isbn'],'cover_url':scov,'price':None}})
    (ROOT/'data'/'seeds'/'special-edition-fix-ndl.yml').write_text(
        "# 残りの仕上げ: NDLで通常版ISBN取得→楽天で書影。 通常版主+特装variant(案B)。\n"+
        yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False),encoding='utf-8')
    with (ROOT/'.cache'/'genre-rakuten'/'sef-ndl-review.tsv').open('w',encoding='utf-8') as fh:
        fh.write('title\tvol\tversion\tspecial_isbn\tstatus\n')
        for r in review: fh.write('\t'.join(str(x) for x in r)+'\n')
    print(f'\n採用 {len(corr)} / なお未取得 {len(review)}',flush=True)

if __name__=='__main__': main()
