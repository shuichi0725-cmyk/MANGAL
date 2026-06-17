#!/usr/bin/env python3
"""
特装版混入 修正(a)の補助: 通常版ISBNの書影が楽天収穫に無い分を、楽天APIで取得して seed に充填。
(書影は元々すべて楽天由来。 通常版ISBN自体は種1の兄弟=確定。 これは書影だけ補う)
レート制限(429)に配慮して sleep+retry。
"""
import json,time,urllib.request,urllib.parse,urllib.error,sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
env={}
for ln in open(ROOT/'.env.local',encoding='utf-8'):
    if '=' in ln: k,v=ln.split('=',1); env[k.strip()]=v.strip()
from urllib.parse import urlparse
ref=env.get('RAKUTEN_REFERER','https://github.com/'); o=urlparse(ref); origin=f'{o.scheme}://{o.netloc}'

def fetch_cover(isbn):
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'format':'json','formatVersion':'2','isbn':isbn,'hits':1}
    u='https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?'+urllib.parse.urlencode(p)
    req=urllib.request.Request(u,headers={'Referer':ref,'Origin':origin,'User-Agent':'MANGAL-DataFetch/0.1','Accept':'application/json'})
    for attempt in range(4):
        try:
            d=json.loads(urllib.request.urlopen(req,timeout=25).read())
            its=d.get('Items') or []
            if not its: return None
            b=its[0]
            url=b.get('largeImageUrl') or b.get('mediumImageUrl') or ''
            if not url or 'noimage' in url: return None
            return url.split('?')[0]+'?_ex=200x200'
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(1.5*(attempt+1)); continue
            return None
        except Exception:
            time.sleep(0.5); continue
    return None

def main():
    fp=ROOT/'data'/'seeds'/'special-edition-fix.yml'
    raw=fp.read_text(encoding='utf-8')
    hdr='\n'.join(l for l in raw.splitlines() if l.startswith('#'))
    doc=yaml.safe_load(raw)
    corr=doc['corrections']
    todo=[x for x in corr if not x.get('normal_cover')]
    print(f'通常版書影が無い: {len(todo)} 件を楽天取得',flush=True)
    got=0
    for n,x in enumerate(todo,1):
        cv=fetch_cover(x['normal_isbn'])
        if cv: x['normal_cover']=cv; got+=1
        if n%50==0: print(f'  {n}/{len(todo)} (取得 {got})',flush=True)
        time.sleep(0.25)
    fp.write_text(hdr+'\n'+yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False),encoding='utf-8')
    still=sum(1 for x in corr if not x.get('normal_cover'))
    print(f'\n書影補充 {got} 件 / 残り書影無し {still} 件(=書影非表示で許容/CoverImageがonErrorで隠す)',flush=True)

if __name__=='__main__': main()
