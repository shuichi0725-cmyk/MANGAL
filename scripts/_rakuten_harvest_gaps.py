#!/usr/bin/env python3
"""
楽天種(harvest)へのフルデータ追加: manga.v2 の cover_url 無し巻ISBN(歯抜け)を
楽天APIで引き(outOfStockFlag=1 + affiliateId)、 返ってきたフルレコードを純粋追加。
- ★affiliateId 必須(アフィリンク取得)。 ~1req/sec 厳守(time.sleep(1.0))。
- 既に楽天種にあるISBNはskip。 中断再開可(出力jsonlを読み戻してdone判定)。
- 出力: .cache/rakuten-gaps-harvest.jsonl(1行 {"isbn","item"})。 完了後 merge→ data/seeds/harvest 再生成は別途。

使い方: python _rakuten_harvest_gaps.py  [--limit N]
"""
import sys,json,time,urllib.request,urllib.parse
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
AFF=env.get('RAKUTEN_AFFILIATE_ID','')
OUT=ROOT/'.cache'/'rakuten-gaps-harvest.jsonl'
SEED=ROOT/'.cache'/'rakuten-isbn.jsonl'   # 既存楽天種(復元済)

LIMIT=None
for i,a in enumerate(sys.argv):
    if a=='--limit' and i+1<len(sys.argv): LIMIT=int(sys.argv[i+1])

def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def fetch(isbn):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],
       'affiliateId':AFF,'format':'json','formatVersion':'2','isbn':isbn,'hits':1,'outOfStockFlag':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    for at in range(4):
        try:
            d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={'Referer':RREF,'Origin':RORG,'User-Agent':'MANGAL/0.1','Accept':'application/json'}),timeout=25).read())
            its=d.get('Items') or []
            return its[0] if its else None
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(1.5*(at+1)); continue
            return None
        except Exception:
            time.sleep(0.5)
    return None

def main():
    t0=time.time()
    # gap ISBN = 元の歯抜けISBN全部(cover-fill-cache のキー=書影補完が埋めた分も含む)。
    # → 書影が埋まった巻も フルデータ(価格/アフィ/あらすじ)を取りに行く。
    cc=ROOT/'.cache'/'cover-fill-cache.json'
    gaps=set()
    if cc.exists():
        for k in json.loads(cc.read_text(encoding='utf-8')).keys():
            ib=to13(k)
            if ib: gaps.add(ib)
    else:
        for fp in (ROOT/'data'/'manga.v2').glob('*.yml'):
            try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
            except: continue
            if not isinstance(d,dict): continue
            for e in (d.get('editions') or []):
                for v in (e.get('volumes') or []):
                    if not v.get('cover_url'):
                        ib=to13(v.get('isbn13'))
                        if ib: gaps.add(ib)
    print(f'gap ISBN(元歯抜け): {len(gaps):,} [{time.time()-t0:.0f}s]',flush=True)
    # 既存楽天種のISBN(skip)
    have=set()
    if SEED.exists():
        for line in SEED.open(encoding='utf-8'):
            try: r=json.loads(line); i=to13(r.get('isbn') or (r.get('item') or {}).get('isbn'))
            except: continue
            if i: have.add(i)
    print(f'既存楽天種ISBN: {len(have):,} / 収穫対象(種に無い gap): {len(gaps-have):,}',flush=True)
    # 既に収穫済(再開)
    done=set()
    if OUT.exists():
        for line in OUT.open(encoding='utf-8'):
            try: done.add(json.loads(line)['isbn'])
            except: continue
    todo=sorted((gaps-have)-done)
    if LIMIT: todo=todo[:LIMIT]
    print(f'今回収穫: {len(todo):,}(既収穫 {len(done):,} skip)',flush=True)
    f=OUT.open('a',encoding='utf-8')
    hit=0
    for n,ib in enumerate(todo,1):
        it=fetch(ib)
        f.write(json.dumps({'isbn':ib,'item':it},ensure_ascii=False)+'\n'); f.flush()
        if it: hit+=1
        if n%200==0: print(f'  {n}/{len(todo)} データ有{hit} [{time.time()-t0:.0f}s]',flush=True)
    f.close()
    print(f'\n収穫完了: {len(todo)}件照会 / フルデータ取得 {hit} / → {OUT}',flush=True)
    print('※ data/seeds/harvest への merge & .gz 再生成は別途(完了確認後)',flush=True)

if __name__=='__main__': main()
