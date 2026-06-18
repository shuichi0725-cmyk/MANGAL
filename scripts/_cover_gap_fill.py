#!/usr/bin/env python3
"""
歯抜け書影の補完(慎重・純粋追加)。 cover_url が null の巻だけを、ISBNで書影取得して埋める。
取得順: ①楽天CDN構築URL(cabinet/<下4桁>/<isbn>.jpg、suffix _1_2/_1_4)をHTTP検証(API不要・速い)
        ②ダメなら楽天API(isbn照会, outOfStockFlag=1, 1.0秒/件)
対象: 歯抜け(0<cov<total)作品の先頭 N 作(glob sorted・決定的)。 既存cover/他フィールドは不変。

使い方: python _cover_gap_fill.py [N]  (既定100) [--dry-run]
出力: data/manga.v2 と .preview-data/manga を更新 + cover-fill-changelog.jsonl + バックアップ
"""
import sys,re,io,json,time,shutil,urllib.request,urllib.parse
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
RREF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(RREF); RORG=f'{_o.scheme}://{_o.netloc}'

N=100; DRY='--dry-run' in sys.argv
for a in sys.argv[1:]:
    if a.isdigit(): N=int(a)

def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def cdn_ok(url):
    try:
        r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=10)
        d=r.read()
        return 'image' in r.headers.get('Content-Type','') and len(d)>2000
    except Exception: return False
def cover_cdn(isbn):
    for suf in ('.jpg','_1_2.jpg','_1_4.jpg'):
        u=f'https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{isbn[-4:]}/{isbn}{suf}?_ex=200x200'
        if cdn_ok(u): return u
        time.sleep(0.05)
    return None
def cover_api(isbn):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'format':'json','formatVersion':'2','isbn':isbn,'hits':1,'outOfStockFlag':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read())
        its=d.get('Items') or []
        if its:
            url=its[0].get('largeImageUrl') or ''
            if url and 'noimage' not in url: return url.split('?')[0]+'?_ex=200x200'
    except Exception: pass
    return None

def main():
    # 1) 全歯抜けを popularity 降順で収集 → 上位N(人気作=北斗の拳側の実力を測る)
    BYPOP='--by-pop' in sys.argv
    pool=[]  # (pop, slug, gaps)
    t0=time.time()
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        tot=0; cov=0; gaps=[]
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                tot+=1
                if v.get('cover_url'): cov+=1
                else:
                    ib=to13(v.get('isbn13'))
                    if ib: gaps.append(ib)
        if tot>0 and 0<cov<tot and gaps:
            pool.append((d.get('popularity') or 0, d.get('slug'), gaps))
            if not BYPOP and len(pool)>=N: break
    if BYPOP: pool.sort(key=lambda x:-x[0])
    targets=[(s,g) for _,s,g in pool[:N]]
    gap_isbns=sorted({i for _,g in targets for i in g})
    print(f'歯抜け先頭{len(targets)}作 / 欠けISBN(ISBN有){len(gap_isbns)} [{time.time()-t0:.0f}s]',flush=True)

    # 2) 書影取得(CDN先, ダメなら API)。 ISBN結果をキャッシュ=中断耐性・冪等。
    CDNONLY='--cdn-only' in sys.argv
    cachef=ROOT/'.cache'/'cover-fill-cache.json'
    try: ccache=json.loads(cachef.read_text(encoding='utf-8')) if cachef.exists() else {}
    except: ccache={}
    cover={}; new=0
    for n,ib in enumerate(gap_isbns,1):
        if ib in ccache:
            c=ccache[ib]
        else:
            c=cover_cdn(ib)
            if not c and not CDNONLY: c=cover_api(ib)
            ccache[ib]=c; new+=1
            if new%200==0: cachef.write_text(json.dumps(ccache,ensure_ascii=False),encoding='utf-8')
        if c: cover[ib]=c
        if n%500==0: print(f'  {n}/{len(gap_isbns)} 取得{len(cover)} (新規照会{new}) [{time.time()-t0:.0f}s]',flush=True)
    cachef.write_text(json.dumps(ccache,ensure_ascii=False),encoding='utf-8')
    print(f'書影取得: {len(cover)}/{len(gap_isbns)} (新規照会{new}/キャッシュ{len(gap_isbns)-new})',flush=True)
    if DRY:
        print('[DRY] 適用せず終了'); return

    # 3) 適用(null cover の巻だけ純粋追加) — manga.v2 と preview
    bak=ROOT/'.cache'/f'cover-fill-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    clog=[]; filled=0; files=0
    slugs=[s for s,_ in targets]
    for base in (ROOT/'data'/'manga.v2', ROOT/'.preview-data'/'manga'):
        for slug in slugs:
            fp=base/f'{slug}.yml'
            if not fp.exists(): continue
            raw=fp.read_text(encoding='utf-8')
            hdr=raw.split('\n',1)[0] if raw.startswith('#') else None
            d=yaml.load(raw,Loader=L)
            ch=False
            for e in (d.get('editions') or []):
                for v in (e.get('volumes') or []):
                    if v.get('cover_url'): continue
                    ib=to13(v.get('isbn13'))
                    if ib in cover:
                        v['cover_url']=cover[ib]; ch=True
                        if base.name=='manga.v2':
                            filled+=1; clog.append({'slug':slug,'number':v.get('number'),'isbn13':ib,'cover_url':cover[ib]})
            if ch:
                files+=1
                shutil.copy2(fp,bak/(base.name+'__'+fp.name))
                buf=io.StringIO()
                if hdr: buf.write(hdr+'\n')
                yaml.dump(d,buf,allow_unicode=True,sort_keys=False,default_flow_style=False)
                fp.write_text(buf.getvalue(),encoding='utf-8')
    if clog:
        with (ROOT/'data'/'seeds'/'cover-fill-changelog.jsonl').open('a',encoding='utf-8') as f:
            st=time.strftime('%Y-%m-%dT%H:%M:%S')
            for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'\n補完: {filled}巻 (本番) / 更新ファイル{files}(両環境) / backup {bak.name}',flush=True)
    print(f'歯抜け{len(targets)}作中、欠け{len(gap_isbns)}巻 → 埋まった{len(cover)}巻 = {100*len(cover)//max(len(gap_isbns),1)}%',flush=True)

if __name__=='__main__': main()
