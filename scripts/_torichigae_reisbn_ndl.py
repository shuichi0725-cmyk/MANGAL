#!/usr/bin/env python3
"""
空ラベルのNDL RE_ISBN(楽天で埋まらなかった分)。NDL title+author→巻ISBN+楽天書影で再構築。
NDLでも見つからない=本物データ無 → 作品ファイル削除(空はschema違反)+ needs-content記録。
backup+changelog・可逆。
"""
import sys,re,json,time,shutil,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
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
def lnm(t): return t.split('}')[-1]
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def names(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p); p=re.sub(r'[\s　・。.]','',p)
        if len(p)>=2: out.add(hk(p).lower())
    return out
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def pvol(t):
    t=zen(str(t)); m=re.search(r'[（(](\d{1,3})[）)]|[．.]\s*(\d{1,3})\s*$|第(\d{1,3})巻',t)
    return int(next(g for g in m.groups() if g)) if m else 1
def ndl(title):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'50','query':f'title="{title}" AND ndc=726'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'MANGAL/0.1'}),timeout=30).read(); break
        except Exception:
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
        if t and isbn: out.append({'title':t,'isbn':isbn,'auth':names(auth)})
    return out
def rk_cover(isbn):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,'format':'json','formatVersion':'2','isbn':isbn,'hits':1,'outOfStockFlag':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    try:
        its=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=20).read()).get('Items') or []
        if its:
            u2=its[0].get('largeImageUrl') or ''; sd=its[0].get('salesDate') or ''
            cov=(u2.split('?')[0]+'?_ex=200x200') if u2 and 'noimage' not in u2 else None
            m=re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})',sd); rd=f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else None
            return cov,rd
    except: pass
    return None,None

def main():
    slugs=[s.strip() for s in (ROOT/'data'/'seeds'/'torichigae-still-empty.txt').read_text(encoding='utf-8').splitlines() if s.strip()]
    print(f'NDL RE_ISBN 対象 {len(slugs)}',flush=True)
    bak=ROOT/'.cache'/f'reisbn-ndl-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    lf=(ROOT/'data'/'seeds'/'torichigae-reisbn-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    filled=0; removed=[]
    for i,slug in enumerate(slugs,1):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        if d.get('editions'): continue
        title=d.get('title') or ''; wa=set()
        for a in (d.get('authors') or [])+(d.get('original_authors') or []): wa|=names(a.get('name') if isinstance(a,dict) else a)
        time.sleep(1.0); recs=ndl(title)
        vol={}
        for r in recs:
            if wa and not (wa & r['auth']): continue
            n=pvol(r['title']); ib=to13(r['isbn'])
            if ib and n not in vol: vol[n]=ib
        if vol:
            nv=[]
            for n in sorted(vol):
                cov,rd=rk_cover(vol[n]); vv={'number':n,'isbn13':vol[n]}
                if cov: vv['cover_url']=cov
                if rd: vv['release_date']=rd
                nv.append(vv)
            d['editions']=[{'type':'standard','label':'通常版','publisher':d.get('publisher'),'volumes':nv}]
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            filled+=1; lf.write(json.dumps({'slug':slug,'ndl_refill':len(nv),'at':st},ensure_ascii=False)+'\n')
        else:
            # 本物データ無 → 空はschema違反なので削除(記録して後日再追加可)
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.unlink()
            removed.append((slug,title,';'.join(sorted(wa))))
        if i%30==0: print(f'  {i}/{len(slugs)} filled{filled} removed{len(removed)}',flush=True)
    lf.close()
    with (ROOT/'data'/'seeds'/'torichigae-needs-content.tsv').open('w',encoding='utf-8') as f:
        f.write('slug\ttitle\tauthors\n')
        for s,t,a in removed: f.write(f'{s}\t{t}\t{a}\n')
    print(f'\nNDL RE_ISBN完了: 追加再構築 {filled} / 本物データ無で削除 {len(removed)}(needs-content.tsv=後日再追加可)')

if __name__=='__main__': main()
