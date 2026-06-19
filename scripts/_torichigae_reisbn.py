#!/usr/bin/env python3
"""
取り違え是正 段階4=RE_ISBN。空化したラベル作に「ラベル本来の巻」を楽天で再構築。
楽天 title+author(著者一致・outOfStockFlag=1) → 巻+ISBN+書影+発売日。 見つからなければ空のままflag。
backup+changelog・可逆。
"""
import sys,re,json,time,shutil,unicodedata,urllib.request,urllib.parse
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
    t=zen(t); m=re.search(r'[（(](\d{1,3})[）)]|\s(\d{1,3})\s*$|第(\d{1,3})巻',t)
    return int(next(g for g in m.groups() if g)) if m else 1
def rk(title,author):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,'format':'json','formatVersion':'2','title':title,'hits':30,'booksGenreId':'001001','outOfStockFlag':1}
    if author: p['author']=author
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    for at in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read()).get('Items') or []
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(2); continue
            return []
        except Exception: time.sleep(0.5)
    return []

def main():
    slugs=[s.strip() for s in (ROOT/'data'/'seeds'/'torichigae-emptied-labels.txt').read_text(encoding='utf-8').splitlines() if s.strip()]
    print(f'空化ラベル {len(slugs)} を RE_ISBN',flush=True)
    bak=ROOT/'.cache'/f'reisbn-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    lf=(ROOT/'data'/'seeds'/'torichigae-reisbn-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    filled=0; empty=[]
    for i,slug in enumerate(slugs,1):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        if d.get('editions'): continue   # 既に巻あり=skip
        title=d.get('title') or ''; wa=set()
        for a in (d.get('authors') or [])+(d.get('original_authors') or []): wa|=names(a.get('name') if isinstance(a,dict) else a)
        its=rk(title, sorted(wa)[0] if wa else '')
        vol={}
        for b in its:
            if wa and not (names(b.get('author')) & wa): continue
            t=b.get('title','')
            if any(k in t for k in ('特装','限定','イラスト集','画集','設定資料','ガイド','ファンブック')): continue
            ib=to13(b.get('isbn'))
            if not ib: continue
            n=pvol(t); u=b.get('largeImageUrl') or ''
            cov=(u.split('?')[0]+'?_ex=200x200') if u and 'noimage' not in u else None
            sd=b.get('salesDate') or ''; m=re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})',sd) or re.search(r'(\d{4})',sd)
            rd=f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if (m and m.lastindex and m.lastindex>=3) else (m.group(1) if m else None)
            if n not in vol:
                vv={'number':n,'isbn13':ib}
                if cov: vv['cover_url']=cov
                if rd: vv['release_date']=rd
                vol[n]=vv
        if vol:
            nv=[vol[k] for k in sorted(vol)]
            d['editions']=[{'type':'standard','label':'通常版','publisher':d.get('publisher'),'volumes':nv}]
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists():
                    shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml'))
                    f2.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            filled+=1; lf.write(json.dumps({'slug':slug,'refilled_vols':len(nv),'at':st},ensure_ascii=False)+'\n')
        else:
            empty.append(slug)
        if i%30==0: print(f'  {i}/{len(slugs)} filled{filled}',flush=True)
    lf.close()
    (ROOT/'data'/'seeds'/'torichigae-still-empty.txt').write_text('\n'.join(empty),encoding='utf-8')
    print(f'\nRE_ISBN完了: 再構築 {filled} / 本物も見つからず空のまま {len(empty)}(torichigae-still-empty.txt)')

if __name__=='__main__': main()
