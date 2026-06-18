#!/usr/bin/env python3
"""
NDL(ISBN→題名/巻/シリーズ/著者) 収集。第3オラクル(メタのみ・画像不使用)。
入力ISBN群を NDL SRU(isbn=) で引き、cache に蓄積(中断再開・冪等)。~1req/sec。
使い方: python _ndl_isbn_collect.py <isbn-list-source>
  source: 't3'(共有ISBN) / ファイルパス(1行1ISBN) を指定。既定t3。
出力: .cache/ndl-isbn.jsonl  {isbn, title, vol, series, author}
"""
import sys,json,csv,time,re,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'.cache'/'ndl-isbn.jsonl'
def lnm(t): return t.split('}')[-1]
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def ndl_isbn(isbn):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode(
        {'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'2','query':f'isbn="{isbn}"'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'MANGAL/0.1'}),timeout=25).read(); break
        except Exception:
            if at<2: time.sleep(2+at*2); continue
            return None
    try: root=ET.fromstring(b)
    except: return None
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        kids=list(rd); it=rd.iter() if kids else (ET.fromstring(rd.text).iter() if rd.text and '<' in rd.text else [])
        title=vol=ser=auth=None
        for el in it:
            k=lnm(el.tag); t=(el.text or '').strip()
            if not t: continue
            if k=='title' and not title: title=t
            if k=='volume' and not vol: vol=t
            if k=='seriesTitle' and not ser: ser=t
            if k=='creator' and not auth: auth=t
        return {'title':title,'vol':vol,'series':ser,'author':auth}
    return {}

def main():
    src=sys.argv[1] if len(sys.argv)>1 else 't3'
    isbns=[]
    if src=='t3':
        seen=set()
        with open(ROOT/'data'/'seeds'/'t3-ownership.tsv',encoding='utf-8-sig') as f:
            r=csv.reader(f,delimiter='\t'); next(r)
            for x in r:
                ib=to13(x[0])
                if ib and ib not in seen: seen.add(ib); isbns.append(ib)
    else:
        for ln in open(src,encoding='utf-8'):
            ib=to13(ln.strip())
            if ib: isbns.append(ib)
    done=set()
    if OUT.exists():
        for ln in OUT.open(encoding='utf-8'):
            try: done.add(json.loads(ln)['isbn'])
            except: pass
    todo=[i for i in isbns if i not in done]
    print(f'NDL収集: 対象{len(isbns):,} / 既収集{len(done):,} / 今回{len(todo):,}',flush=True)
    t0=time.time(); f=OUT.open('a',encoding='utf-8'); hit=0
    for n,ib in enumerate(todo,1):
        time.sleep(1.0)
        r=ndl_isbn(ib)
        f.write(json.dumps({'isbn':ib,**(r or {})},ensure_ascii=False)+'\n'); f.flush()
        if r and r.get('title'): hit+=1
        if n%100==0: print(f'  {n}/{len(todo)} 取得{hit} [{time.time()-t0:.0f}s]',flush=True)
    f.close()
    print(f'完了: {len(todo)}照会 / メタ取得{hit} → {OUT}',flush=True)

if __name__=='__main__': main()
