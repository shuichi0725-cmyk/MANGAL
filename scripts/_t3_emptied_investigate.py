#!/usr/bin/env python3
"""
空化40作(全巻が他作ISBN)の仕分け。 drop(丸ごと別作の重複) か 再ISBN(実在作だがISBN全部誤) か。
判定: NDL題名検索で「その作品の著者」に一致する別ISBNが在れば=実在作→再ISBN候補。 無ければ=重複→drop候補。
読み取りのみ。 出力 data/seeds/t3-emptied-triage.tsv
"""
import sys,csv,json,re,time,urllib.request,urllib.parse,unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def lnm(t): return t.split('}')[-1]
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|story|art)$')
def na(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;・\s]+',s):
        p=re.sub(r'^\[[^\]]*\]','',p.strip()); p=ROLE.sub('',p).strip()
        if len(p)>=2: out.add(p.lower())
    return out

def ndl_title(title):
    q=f'title="{title}" AND ndc=726'
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'50','query':q})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'MANGAL/0.1'}),timeout=25).read(); break
        except Exception:
            if at<2: time.sleep(2); continue
            return []
    try: root=ET.fromstring(b)
    except: return []
    out=[]
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        kids=list(rd); it=rd.iter() if kids else (ET.fromstring(rd.text).iter() if rd.text and '<' in rd.text else [])
        isbn=auth=None
        for el in it:
            k=lnm(el.tag); t=(el.text or '').strip()
            if not t: continue
            if k=='identifier' and not isbn:
                m=re.search(r'97[89]\d{10}',t.replace('-','')); isbn=m.group() if m else None
            if k=='creator' and not auth: auth=t
        if isbn: out.append({'isbn':isbn,'author':na(auth)})
    return out

def main():
    # owner ISBNs per emptied slug (t3-consensus)
    cons={}
    with open(ROOT/'data'/'seeds'/'t3-consensus.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r: cons.setdefault(x[6],set()).add(to13(x[0]))
    emptied=[]
    with open(ROOT/'data'/'seeds'/'t3-deferred-emptied.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            if x: emptied.append(x[0])
    out=[]; t0=time.time()
    for i,slug in enumerate(emptied,1):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        title=d.get('title') or ''
        wauth=set()
        for a in (d.get('authors') or []): wauth|=na(a.get('name') if isinstance(a,dict) else a)
        owner_isbns=cons.get(slug,set())
        time.sleep(1.0)
        recs=ndl_title(title)
        # その作の著者に一致 かつ owner ISBN でない = 独立実在の証拠
        own=[r for r in recs if r['isbn'] not in owner_isbns and (wauth & r['author'])]
        verdict='再ISBN候補(実在)' if own else 'drop候補(独立記録なし)'
        out.append([slug,title,';'.join(sorted(wauth))[:24],len(owner_isbns),len(recs),len(own),
                    (own[0]['isbn'] if own else ''),verdict])
        if i%10==0: print(f'  {i}/{len(emptied)} [{time.time()-t0:.0f}s]',flush=True)
    p=ROOT/'data'/'seeds'/'t3-emptied-triage.tsv'
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['slug','title','author','owner_isbn_n','ndl_hits','own_isbn_hits','own_isbn_sample','verdict'])
        for r in out: w.writerow(r)
    from collections import Counter
    print('仕分け:',dict(Counter(r[7] for r in out)))
    print('-- drop候補 --')
    for r in out:
        if r[7].startswith('drop'): print(f'  {r[0]}「{r[1][:18]}」著={r[2]} (NDL hit {r[4]}, 自著一致0)')
    print('-- 再ISBN候補 --')
    for r in out:
        if r[7].startswith('再'): print(f'  {r[0]}「{r[1][:18]}」著={r[2]} → 自ISBN例 {r[6]}')
    print(f'→ {p}')

if __name__=='__main__': main()
