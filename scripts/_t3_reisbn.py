#!/usr/bin/env python3
"""
T3再ISBN(慎重): 全巻が他作ISBNだった作(deferred-emptied)を、楽天で著者一致の正ISBN一覧に組み直す。
- 楽天 title+author 検索(outOfStockFlag=1)→ 著者一致＋題コア一致＋非特装 の本だけ採用。
- 巻番号でdedup(画像有優先)→ standard版を再構築。 1作も著者一致が無ければスキップ(=2ソース不在→drop保留)。
- 可逆: 旧volumesをchangelogに記録。 preview+manga.v2。
使い方: python _t3_reisbn.py [--apply]   (既定dry-run)
"""
import sys,io,json,csv,re,time,shutil,unicodedata,urllib.request,urllib.parse
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
APPLY='--apply' in sys.argv
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
SP=('特装','限定','フィギュア','ドラマcd','同梱','付き','付録','豪華','box','缶バッジ','アクリル','カレンダー','小冊子','特典','初回','特別','dvd','ぬいぐるみ','セット')
def is_sp(t): return any(k in t.lower() for k in SP)
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが)$')
def na(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;・\s]+',s):
        p=re.sub(r'^\[[^\]]*\]','',p.strip()); p=ROLE.sub('',p).strip()
        if len(p)>=2: out.add(p.lower())
    return out
def ncore(s):
    s=zen(s); s=unicodedata.normalize('NFKC',s)
    s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    return re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
def parse_vol(title):
    t=zen(str(title)).strip()
    for pat in (r'[（(](\d{1,4})[）)]', r'第(\d{1,4})\s*巻', r'(\d{1,4})\s*巻', r'vol[\.．]?\s*(\d{1,4})', r'〈(\d{1,4})〉'):
        m=re.search(pat,t,re.I)
        if m: return int(m.group(1))
    m=re.search(r'[\s　](\d{1,3})\s*$', t)
    return int(m.group(1)) if m else None

def rk_search(title,author):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,
       'format':'json','formatVersion':'2','title':title,'author':author,'hits':30,'booksGenreId':'001001','outOfStockFlag':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'M/0.1','Accept':'application/json'}),timeout=25).read())
        return d.get('Items') or []
    except Exception: return []

def load_cm104():
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata104.json',encoding='utf-8'))
    g=g.get('@graph',g) if isinstance(g,dict) else g
    from collections import defaultdict
    idx=defaultdict(list)
    def cnm(r):
        v=r.get('ma:seriesName') or r.get('schema:name'); return v[0] if isinstance(v,list) else v
    for r in g:
        idx[ncore(cnm(r))].append(r)
    return idx

def main():
    print('cm104 ロード中...',flush=True)
    CM=load_cm104()
    slugs=[]
    with open(ROOT/'data'/'seeds'/'t3-deferred-emptied.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            if x: slugs.append(x[0])
    print(f'対象(空化){len(slugs)} を楽天で再構築判定 (apply={APPLY})',flush=True)
    rebuilt=[]; skipped=[]; t0=time.time(); clog=[]
    bak=ROOT/'.cache'/f't3-reisbn-bak-{time.strftime("%Y%m%d-%H%M%S")}'
    for n,slug in enumerate(slugs,1):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        title=d.get('title') or ''; wa=set()
        for a in (d.get('authors') or []): wa|=na(a.get('name') if isinstance(a,dict) else a)
        wcore=ncore(title)
        items=rk_search(title, ';'.join(sorted(wa)).split(';')[0] if wa else '')
        # 著者一致+題コア一致+非特装
        vol2it={}
        for b in items:
            bt=b.get('title','') ; ba=na(b.get('author'))
            if is_sp(bt): continue
            if wa and not (wa & ba): continue
            bc=ncore(bt)
            if not (wcore[:4] and (wcore[:6] in bc or bc[:6] in wcore)): continue
            vn=parse_vol(bt)
            if vn is None: vn=1
            url=b.get('largeImageUrl') or ''
            cur=(url.split('?')[0]+'?_ex=200x200') if url and 'noimage' not in url else None
            cand={'number':vn,'isbn13':to13(b.get('isbn')),'cover_url':cur,'release_date':b.get('salesDate'),'price':b.get('itemPrice')}
            if vn not in vol2it or (cur and not vol2it[vn]['cover_url']): vol2it[vn]=cand
        newvols=[vol2it[k] for k in sorted(vol2it)]
        if not newvols:
            skipped.append((slug,'楽天著者一致なし')); continue
        # ★cm104で巻数を2ソース確認: 楽天new巻数が cm104の同作いずれかの版巻数と一致する時だけ採用
        eds=[r for r in CM.get(wcore,[]) if (wa & na(r.get('schema:creator')))]
        cm_counts=set()
        for r in eds:
            try: cm_counts.add(int(r.get('schema:numberOfItems')))
            except: pass
        if len(newvols) not in cm_counts:
            skipped.append((slug,f'cm104未確認(楽天{len(newvols)}/cm104{sorted(cm_counts)})')); continue
        oldn=sum(len(e.get('volumes') or []) for e in (d.get('editions') or []))
        rebuilt.append((slug,title,oldn,len(newvols),newvols[0]['isbn13']))
        if APPLY:
            bak.mkdir(parents=True,exist_ok=True)
            clog.append({'slug':slug,'old_editions':d.get('editions'),'new_std_vols':newvols})
            # standard を newvols で置換、他edition(あれば=別物ISBN)は今回は残さず標準のみ再構成
            d['editions']=[{'type':'standard','publisher':d.get('publisher'),'volumes':newvols}]
            shutil.copy2(fp,bak/('manga.v2__'+fp.name))
            buf=io.StringIO(); buf.write(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False)); fp.write_text(buf.getvalue(),encoding='utf-8')
            pf=ROOT/'.preview-data'/'manga'/f'{slug}.yml'
            if pf.exists():
                shutil.copy2(pf,bak/('preview__'+fp.name)); pf.write_text(buf.getvalue(),encoding='utf-8')
        if n%10==0: print(f'  {n}/{len(slugs)} 再構築{len(rebuilt)} skip{len(skipped)} [{time.time()-t0:.0f}s]',flush=True)
    if APPLY and clog:
        with (ROOT/'data'/'seeds'/'t3-reisbn-changelog.jsonl').open('a',encoding='utf-8') as f:
            st=time.strftime('%Y-%m-%dT%H:%M:%S')
            for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'\n再構築(cm104巻数一致=2ソース確認): {len(rebuilt)} / skip: {len(skipped)}',flush=True)
    print('-- 再構築(old巻→new巻・cm104確認済) --')
    for s,t,o,nn,ib in rebuilt: print(f'  {s}「{t[:16]}」 {o}巻→{nn}巻 (正ISBN例 {ib})')
    print('-- skip(理由) --')
    for s,why in skipped: print(f'  {s}: {why}')

if __name__=='__main__': main()
