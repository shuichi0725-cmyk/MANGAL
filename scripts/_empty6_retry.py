#!/usr/bin/env python3
"""空作6を NDL(title+loose著者) + 楽天 で再検索。見つかれば充当(volumes)、ダメなら削除(needs-content)。"""
import sys,re,json,time,shutil,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
from urllib.parse import urlparse
RREF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(RREF); RORG=f'{_o.scheme}://{_o.netloc}'; AFF=env.get('RAKUTEN_AFFILIATE_ID','')
def lnm(t): return t.split('}')[-1]
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|まんが)$')
def na(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;・\s]+',s):
        p=ROLE.sub('',p.strip())
        if len(p)>=2: out.add(hk(p).lower())
    return out
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def pvol(t):
    t=zen(str(t)); m=re.search(r'[（(](\d{1,3})[）)]|[．.]\s*(\d{1,3})\s*$|第(\d{1,3})巻|\s(\d{1,3})$',t)
    return int(next(g for g in m.groups() if g)) if m else 1
def ndl(title):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'80','query':f'title="{title}" AND ndc=726'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'M/0.1'}),timeout=25).read(); break
        except:
            if at<2: time.sleep(2); continue
            return []
    out=[]
    try: root=ET.fromstring(b)
    except: return []
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        kids=list(rd); it=list(rd.iter()) if kids else (list(ET.fromstring(rd.text).iter()) if rd.text and '<' in rd.text else [])
        t=isbn=auth=None
        for el in it:
            k=lnm(el.tag); tx=(el.text or '').strip()
            if not tx: continue
            if k=='title' and not t: t=tx
            if k=='creator' and not auth: auth=tx
            if k=='identifier' and not isbn:
                m=re.search(r'97[89]\d{10}',tx.replace('-','')); isbn=m.group() if m else isbn
        if t and isbn: out.append({'t':t,'isbn':isbn,'au':na(auth)})
    return out
def rk(title,author):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,'format':'json','formatVersion':'2','title':title,'hits':30,'booksGenreId':'001001','outOfStockFlag':1}
    if author: p['author']=author
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read()).get('Items') or []
    except: return []

def main():
    slugs=[x.strip() for x in (ROOT/'data'/'seeds'/'empty-still-unresolved.txt').read_text(encoding='utf-8').splitlines() if x.strip()]
    bak=ROOT/'.cache'/f'empty6-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    filled=0; removed=[]
    for slug in slugs:
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.safe_load(fp.read_text(encoding='utf-8'))
        if d.get('editions'): continue
        title=d.get('title') or ''; wa=set()
        for a in (d.get('authors') or []): wa|=na(a.get('name'))
        vol={}
        # NDL
        for r in ndl(title):
            if wa and not (wa & r['au']): continue
            n=pvol(r['t']); ib=to13(r['isbn'])
            if ib and n not in vol: vol[n]=ib
        time.sleep(1.0)
        # 楽天(NDL空時)
        if not vol:
            for b in rk(title, sorted(wa)[0] if wa else ''):
                if wa and not (na(b.get('author')) & wa): continue
                ib=to13(b.get('isbn'))
                if ib: n=pvol(b.get('title','')); vol.setdefault(n,ib)
        if vol:
            nv=[{'number':n,'isbn13':vol[n]} for n in sorted(vol)]
            d['editions']=[{'type':'standard','label':'通常版','publisher':d.get('publisher'),'volumes':nv}]
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            filled+=1; print(f'  FILL {slug}「{title}」{len(nv)}巻')
        else:
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.unlink()
            removed.append((slug,title)); print(f'  REMOVE {slug}「{title}」(NDL/楽天とも無)')
    with (ROOT/'data'/'seeds'/'torichigae-needs-content.tsv').open('a',encoding='utf-8') as f:
        for s,t in removed: f.write(f'{s}\t{t}\t空作・NDL楽天とも無で削除(後日ISBN見つかれば再追加)\n')
    print(f'\n空作6: 充当{filled} / 削除{len(removed)} backup={bak}')

if __name__=='__main__': main()
