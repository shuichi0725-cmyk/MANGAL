#!/usr/bin/env python3
"""
NOT_FOUND(ローカル未収録)を楽天APIで実在確認(①完成)。
各作 楽天 title+author 検索→著者一致あり=CONFIRMED(実在), 無し=STILL_MISSING(種1調査対象)。
~1req/sec・中断再開(出力を読み戻し)。 出力: data/seeds/notfound-recheck.jsonl
"""
import sys,json,csv,re,time,unicodedata,urllib.request,urllib.parse
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
OUT=ROOT/'.cache'/'notfound-recheck.jsonl'
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def names(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p); p=re.sub(r'[\s　・。.]','',p)
        if len(p)>=2: out.add(hk(p).lower())
    return out
def rk(title,author):
    time.sleep(1.0)
    p={'applicationId':env['RAKUTEN_APP_ID'],'accessKey':env['RAKUTEN_ACCESS_KEY'],'affiliateId':AFF,'format':'json','formatVersion':'2','title':title,'hits':20,'booksGenreId':'001001','outOfStockFlag':1}
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
    nf=[x for x in csv.reader(open(ROOT/'data'/'seeds'/'identity-check.tsv',encoding='utf-8-sig'),delimiter='\t') if x[-1]=='NOT_FOUND']
    done=set()
    if OUT.exists():
        for l in OUT.open(encoding='utf-8'):
            try: done.add(json.loads(l)['slug'])
            except: pass
    todo=[x for x in nf if x[0] not in done]
    print(f'NOT_FOUND {len(nf)} / 既済{len(done)} / 今回{len(todo)}',flush=True)
    f=OUT.open('a',encoding='utf-8'); t0=time.time(); conf=0
    for i,x in enumerate(todo,1):
        slug,title,au=x[0],x[1],set(t for t in x[2].split(';') if t)
        its=rk(title, sorted(au)[0] if au else '')
        hit=any(names(b.get('author')) & au for b in its) if au else bool(its)
        f.write(json.dumps({'slug':slug,'title':title,'status':'CONFIRMED' if hit else 'STILL_MISSING','rk_count':len(its)},ensure_ascii=False)+'\n'); f.flush()
        if hit: conf+=1
        if i%200==0: print(f'  {i}/{len(todo)} 実在確認{conf} [{time.time()-t0:.0f}s]',flush=True)
    f.close()
    print(f'完了: {len(todo)}照会 / 実在CONFIRMED{conf} → {OUT}',flush=True)

if __name__=='__main__': main()
