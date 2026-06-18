#!/usr/bin/env python3
"""
空作23の正ISBN復活(NDL中心・慎重)。各作をNDL title検索→著者一致記録のISBN+巻でstandard再構築。
cm104巻数で裏取り(あれば)。楽天で書影。 --apply で適用(可逆)。 dragon-quest-daino-daibouken はalias。
"""
import sys,re,io,json,time,shutil,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
from urllib.parse import urlparse
RREF=env.get('RAKUTEN_REFERER','https://github.com/'); _o=urlparse(RREF); RORG=f'{_o.scheme}://{_o.netloc}'; AFF=env.get('RAKUTEN_AFFILIATE_ID','')
def lnm(t): return t.split('}')[-1]
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが)$')
def na(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;・\s]+',s):
        p=re.sub(r'^\[[^\]]*\]','',p.strip()); p=ROLE.sub('',p).strip()
        if len(p)>=2: out.add(p.lower())
    return out
def pvol(title):
    t=zen(str(title))
    for pat in (r'[（(](\d{1,3})[）)]', r'[．.]\s*(\d{1,3})\s*$', r'第(\d{1,3})巻', r'(\d{1,3})\s*巻'):
        m=re.search(pat,t)
        if m: return int(m.group(1))
    return None
def ndl_title(title):
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
        kids=list(rd); it=rd.iter() if kids else (ET.fromstring(rd.text).iter() if rd.text and '<' in rd.text else [])
        t=isbn=auth=None
        for el in it:
            k=lnm(el.tag); tx=(el.text or '').strip()
            if not tx: continue
            if k=='title' and not t: t=tx
            if k=='creator' and not auth: auth=tx
            if k=='identifier' and not isbn:
                m=re.search(r'97[89]\d{10}',tx.replace('-','')); isbn=m.group() if m else isbn
        if t and isbn: out.append({'title':t,'isbn':isbn,'auth':na(auth)})
    return out
def rk_cover(isbn):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,'format':'json','formatVersion':'2','isbn':isbn,'hits':1,'outOfStockFlag':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read())
        its=d.get('Items') or []
        if its:
            url=its[0].get('largeImageUrl') or ''
            if url and 'noimage' not in url: return url.split('?')[0]+'?_ex=200x200'
    except: pass
    return None

def main():
    slugs=[s.strip() for s in open(ROOT/'data'/'seeds'/'t3-emptied-unresolved.txt',encoding='utf-8') if s.strip()]
    t0=time.time(); plan={}; skip=[]
    for slug in slugs:
        if slug=='dragon-quest-daino-daibouken': skip.append((slug,'dup→dragon-quest-dai-no-daibouken(alias)')); continue
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.safe_load(fp.read_text(encoding='utf-8'))
        title=d.get('title') or ''; wa=set()
        for a in (d.get('authors') or [])+(d.get('original_authors') or []): wa|=na(a.get('name') if isinstance(a,dict) else a)
        time.sleep(1.0)
        recs=ndl_title(title)
        # 著者一致のみ
        vols={}
        for r in recs:
            if wa and not (wa & r['auth']): continue
            vn=pvol(r['title']) or 1
            if vn not in vols: vols[vn]=to13(r['isbn'])
        if vols:
            plan[slug]={'title':title,'vols':vols}
        else:
            skip.append((slug,f'NDL著者一致なし(recs{len(recs)})'))
    print(f'\n=== 空作23 NDL解決(dry) ===')
    print(f'復活可: {len(plan)} / skip: {len(skip)}')
    for slug,p in plan.items():
        ti=p['title'][:14]; nv=len(p['vols']); ex=list(p['vols'].values())[0]
        print(f'  {slug:30s}「{ti}」 {nv}巻 例ISBN {ex}')
    print('-- skip --')
    for s,why in skip: print(f'  {s}: {why}')
    if not APPLY: print('\n(dry-run)'); return
    bak=ROOT/'.cache'/f'empty23-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    for slug,p in plan.items():
        newvols=[]
        for vn in sorted(p['vols']):
            ib=p['vols'][vn]; cov=rk_cover(ib) if ib else None
            newvols.append({'number':vn,'isbn13':ib,'cover_url':cov})
        for base in ('data/manga.v2','.preview-data/manga'):
            f2=ROOT/base/f'{slug}.yml'
            if not f2.exists(): continue
            d=yaml.safe_load(f2.read_text(encoding='utf-8'))
            shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml'))
            d['editions']=[{'type':'standard','label':'通常版','publisher':d.get('publisher'),'volumes':newvols}]
            f2.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
    with (ROOT/'data'/'seeds'/'empty23-changelog.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for slug,p in plan.items(): f.write(json.dumps({'slug':slug,'restored_vols':len(p['vols']),'applied_at':st},ensure_ascii=False)+'\n')
    print(f'\n適用: 復活{len(plan)}作')

if __name__=='__main__': main()
