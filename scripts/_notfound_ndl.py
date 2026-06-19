#!/usr/bin/env python3
"""
NOT_FOUNDのNDL実在確認(楽天版と並行)。NDL title検索→著者一致あり=CONFIRMED。
~1req/sec・中断再開。 出力: data/seeds/notfound-ndl.jsonl  (楽天版と後で統合: どちらか1つでCONFIRMED)
"""
import sys,json,csv,re,time,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'.cache'/'notfound-ndl.jsonl'
def lnm(t): return t.split('}')[-1]
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー)$')
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def names(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;]+',s):
        p=re.sub(r'[\[【][^\]】]*[\]】]','',p.strip()); p=ROLE.sub('',p); p=re.sub(r'[\s　・。.]','',p)
        if len(p)>=2: out.add(hk(p).lower())
    return out
def ndl(title):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'20','query':f'title="{title}" AND ndc=726'})
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
        auth=None
        for el in it:
            if lnm(el.tag)=='creator' and (el.text or '').strip(): auth=el.text.strip(); break
        out.append(names(auth))
    return out

def main():
    nf=[x for x in csv.reader(open(ROOT/'data'/'seeds'/'identity-check.tsv',encoding='utf-8-sig'),delimiter='\t') if x[-1]=='NOT_FOUND']
    done=set()
    if OUT.exists():
        for l in OUT.open(encoding='utf-8'):
            try: done.add(json.loads(l)['slug'])
            except: pass
    todo=[x for x in nf if x[0] not in done]
    print(f'NDL: NOT_FOUND{len(nf)} / 既済{len(done)} / 今回{len(todo)}',flush=True)
    f=OUT.open('a',encoding='utf-8'); t0=time.time(); conf=0
    for i,x in enumerate(todo,1):
        time.sleep(1.0)
        slug,title,au=x[0],x[1],set(t for t in x[2].split(';') if t)
        recs=ndl(title)
        hit=any(au & r for r in recs) if au else bool(recs)
        f.write(json.dumps({'slug':slug,'status':'CONFIRMED' if hit else 'MISSING','recs':len(recs)},ensure_ascii=False)+'\n'); f.flush()
        if hit: conf+=1
        if i%200==0: print(f'  {i}/{len(todo)} NDL実在{conf} [{time.time()-t0:.0f}s]',flush=True)
    f.close()
    print(f'完了: {len(todo)}照会 / NDL実在{conf} → {OUT}',flush=True)

if __name__=='__main__': main()
