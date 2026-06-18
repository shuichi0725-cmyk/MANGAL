#!/usr/bin/env python3
"""
巻末型歯抜けの書影補完(タイトル検索方式)。 ISBN照会で当たらない=DBのISBNが別版を指す問題に対応。
作品名(+著者)で楽天検索 → 欠け巻番号に一致し表紙ありの item を拾う。
別版誤取得防止: 兄弟(画像あり)巻と同じISBN接頭を優先。
- 純粋追加(cover_url が null の巻のみ)。 誤ISBNは log に記録(後で是正可、ここでは変更しない)。
- 楽天 ~1req/sec。 入力: data/seeds/trailing-cover-gaps.tsv (type=北斗型優先)。

使い方: python _trailing_fill_titlesearch.py [N] [--all-types]
出力: manga.v2 + preview の cover_url、 cover-fill-changelog.jsonl(src=titlesearch)、
      data/seeds/trailing-isbn-mismatch.tsv(DBのISBN≠楽天の正ISBN)
"""
import sys,re,io,csv,json,time,urllib.request,urllib.parse,unicodedata
from pathlib import Path
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
RREF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(RREF); RORG=f'{_o.scheme}://{_o.netloc}'; AFF=env.get('RAKUTEN_AFFILIATE_ID','')

N=None; ALLT='--all-types' in sys.argv
for a in sys.argv[1:]:
    if a.isdigit(): N=int(a)
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

CACHE=ROOT/'.cache'/'trailing-search'; CACHE.mkdir(parents=True,exist_ok=True)
def search(title,author):
    key=re.sub(r'[^\w]','_',(title+'__'+(author or ''))[:60])
    cf=CACHE/(key+'.json')
    if cf.exists():
        try: return json.loads(cf.read_text(encoding='utf-8'))
        except: pass
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,
       'format':'json','formatVersion':'2','title':title,'hits':30,'booksGenreId':'001001','outOfStockFlag':1}
    if author: p['author']=author
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    out=[]
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read())
        for b in (d.get('Items') or []):
            url=b.get('largeImageUrl') or ''
            out.append({'title':b.get('title',''),'isbn':to13(b.get('isbn')),
                        'cover':(url.split('?')[0]+'?_ex=200x200') if url and 'noimage' not in url else None})
    except Exception: pass
    cf.write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
    return out

def author_of(d):
    for k in ('authors','credits'):
        a=d.get(k)
        if isinstance(a,list) and a:
            x=a[0]
            if isinstance(x,dict): return x.get('name') or x.get('display') or x.get('full')
            if isinstance(x,str): return x
    return None

def main():
    # 入力(北斗型優先)
    works=[]
    with open(ROOT/'data'/'seeds'/'trailing-cover-gaps.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            slug,title,std,cov,miss,pct,gstart,typ,mvols,misbn=x
            if not ALLT and typ!='北斗型': continue
            works.append({'slug':slug,'title':title,'mvols':[int(v) for v in mvols.split(',') if v]})
    if N: works=works[:N]
    print(f'対象 {len(works)} 作(北斗型{"" if not ALLT else "+vol1偏"})',flush=True)
    t0=time.time(); filled=0; clog=[]; mism=[]; files_set=set()
    for wi,w in enumerate(works,1):
        if wi%30==0: print(f'  {wi}/{len(works)} 補完{filled} [{time.time()-t0:.0f}s]',flush=True)
        fp=ROOT/'data'/'manga.v2'/f'{w["slug"]}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        au=author_of(d)
        # standard の兄弟ISBN接頭(画像あり巻)
        sib=[]; need={}
        for e in (d.get('editions') or []):
            if e.get('type')!='standard': continue
            for v in (e.get('volumes') or []):
                ib=to13(v.get('isbn13'))
                if v.get('cover_url') and ib: sib.append(ib)
                elif not v.get('cover_url') and isinstance(v.get('number'),(int,float)): need[int(v['number'])]=v
        if not need: continue
        # ★兄弟ISBNの共通接頭が9桁以上(=同一シリーズ番号ブロック)の時だけ採用。
        #   出版社レベル(7桁)止まりだと別エディション(コレクション/PREMIUM)を誤取得するため。
        prefix=None
        if sib:
            from os.path import commonprefix
            cp=commonprefix(sib)
            if len(cp)>=9: prefix=cp   # 烈火 9784091263… の連番型のみ通る
        its=search(w['title'],au)
        if not its: its=search(w['title'],None)
        # 巻番号→候補(表紙あり)
        chosen={}
        for n in need:
            vnpat=re.compile(r'(?<![0-9])'+str(n)+r'(?![0-9])')
            cands=[it for it in its if it['cover'] and vnpat.search(zen(it['title']))]
            if not cands: continue
            # ★接頭一致のみ採用(別版=文庫/大全集等の誤取得を防ぐ)。 接頭不明or不一致は埋めない。
            if not prefix: continue
            pref=[c for c in cands if c['isbn'].startswith(prefix)]
            if pref: chosen[n]=pref[0]
        if not chosen: continue
        # 適用(manga.v2 + preview)
        for base in (ROOT/'data'/'manga.v2', ROOT/'.preview-data'/'manga'):
            bfp=base/f'{w["slug"]}.yml'
            if not bfp.exists(): continue
            raw=bfp.read_text(encoding='utf-8'); hdr=raw.split('\n',1)[0] if raw.startswith('#') else None
            dd=yaml.load(raw,Loader=L); ch=False
            for e in (dd.get('editions') or []):
                if e.get('type')!='standard': continue
                for v in (e.get('volumes') or []):
                    n=v.get('number')
                    if v.get('cover_url') or not isinstance(n,(int,float)): continue
                    n=int(n)
                    if n in chosen:
                        v['cover_url']=chosen[n]['cover']; ch=True
                        if base.name=='manga.v2':
                            filled+=1
                            our=to13(v.get('isbn13')); fnd=chosen[n]['isbn']
                            clog.append({'slug':w['slug'],'number':n,'isbn13':our,'cover_url':chosen[n]['cover'],'src':'titlesearch','found_isbn':fnd})
                            if our and fnd and our!=fnd: mism.append([w['slug'],n,our,fnd,chosen[n]['title'][:30]])
            if ch:
                files_set.add(str(bfp)); buf=io.StringIO()
                if hdr: buf.write(hdr+'\n')
                yaml.dump(dd,buf,allow_unicode=True,sort_keys=False,default_flow_style=False)
                bfp.write_text(buf.getvalue(),encoding='utf-8')
    if clog:
        with (ROOT/'data'/'seeds'/'cover-fill-changelog.jsonl').open('a',encoding='utf-8') as f:
            st=time.strftime('%Y-%m-%dT%H:%M:%S')
            for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    with (ROOT/'data'/'seeds'/'trailing-isbn-mismatch.tsv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','volume','db_isbn','rakuten_isbn','rakuten_title'])
        for r in mism: w.writerow(r)
    print(f'\n補完: {filled}巻(本番) / 更新ファイル{len(files_set)} / ISBN不一致 {len(mism)}件 → trailing-isbn-mismatch.tsv',flush=True)

if __name__=='__main__': main()
