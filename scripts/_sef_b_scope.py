#!/usr/bin/env python3
"""
(b)化物語型のスコープ確定: 種1で「おまけ特装/限定だが通常版兄弟が種1に無い」かつ本番manga.v2に実在する巻を、
作品単位で洗い出す(著者付き=楽天検索の鍵)。出力: .cache/genre-rakuten/sef-b-targets.json + 集計。
"""
import json,re,sqlite3,time,subprocess,sys
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L

def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
        return None
    return v
def vnorm(v):
    try: return str(int(float(v)))
    except: return str(v or '')
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 else s
OMAKE=('特装','限定','フィギュア','ドラマCD','同梱','付き','付','豪華','エキスパンション','BOX','缶バッジ','アクリル','カレンダー','小冊子','特典','初回')
def is_omake(v):
    return bool(v) and any(k in v for k in OMAKE) and not any(k in v for k in ('文庫','新書','新装版','完全版','愛蔵版'))

def main():
    t0=time.time()
    g=json.load(open('.cache/madb/metadata101.json',encoding='utf-8'))['@graph']
    recs=defaultdict(list); isbn2rec={}
    for r in g:
        if r.get('@type')!='class:MangaBook': continue
        cr=first(r.get('dcterms:creator')); cr=cr.get('@id') if isinstance(cr,dict) else (cr or '')
        nm=first(r.get('schema:name')) or first(r.get('rdfs:label')) or ''
        vn=vnorm(first(r.get('schema:volumeNumber')))
        isbn=to13(first(r.get('schema:isbn')))
        rec={'ver':(first(r.get('schema:version')) or '').strip(),'date':first(r.get('schema:datePublished')),'isbn':isbn,'key':(str(cr),str(nm),vn)}
        recs[rec['key']].append(rec)
        if isbn: isbn2rec[isbn]=rec
    print(f'[{time.time()-t0:.0f}s] 種1 index',flush=True)
    # (b) special isbns = omake & no empty sibling, restricted to db-v2 standard
    c=sqlite3.connect('.cache/db-v2.sqlite')
    std=set(to13(i) for (i,) in c.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.type='standard' AND v.isbn13 IS NOT NULL"))
    bset={}
    for i in std:
        r=isbn2rec.get(i)
        if not r or not is_omake(r['ver']): continue
        sib=[x for x in recs[r['key']] if not x['ver'] and x['isbn'] and x['isbn']!=i]
        if sib: continue  # (a)
        bset[i]={'ver':r['ver'],'date':r['date'],'name':r['key'][1],'vol':r['key'][2]}
    print(f'(b)候補 special isbn(db-v2 standard内): {len(bset):,}',flush=True)
    Path('.cache/sef-b-isbns.txt').write_text('\n'.join(bset.keys()),encoding='utf-8')
    # production presence via rg
    try:
        out=subprocess.run(['rg','-l','-F','-f','.cache/sef-b-isbns.txt','data/manga.v2/'],capture_output=True,text=True,timeout=600)
        files=[Path(p) for p in out.stdout.splitlines() if p.strip()]
    except Exception as e:
        files=list((ROOT/'data'/'manga.v2').glob('*.yml')); print('rgなし全走査',e)
    works={}
    for fp in files:
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        if not isinstance(d,dict): continue
        slug=d.get('slug'); title=d.get('title')
        au=[a.get('name') for a in (d.get('authors') or []) if a.get('name') and a.get('name')!='(unknown)']
        vols=[]
        for e in (d.get('editions') or []):
            if e.get('type')!='standard': continue
            for v in (e.get('volumes') or []):
                i=to13(v.get('isbn13'))
                if i in bset:
                    vols.append({'number':v.get('number'),'special_isbn':i,'version':bset[i]['ver'],'date':bset[i]['date']})
        if vols:
            works[slug]={'title':title,'authors':au,'vols':vols}
    nv=sum(len(w['vols']) for w in works.values())
    Path('.cache/genre-rakuten/sef-b-targets.json').write_text(json.dumps(works,ensure_ascii=False,indent=1),encoding='utf-8')
    print(f'\n★本番に実在する(b): {len(works):,}作品 / {nv:,}巻',flush=True)
    noauth=sum(1 for w in works.values() if not w['authors'])
    print(f'  著者不明(楽天検索が弱い): {noauth} 作品',flush=True)
    print('-- サンプル --',flush=True)
    for sl,w in list(works.items())[:12]:
        au='/'.join(w['authors']) or '?'
        nums=[v['number'] for v in w['vols']]
        print("  "+str(w['title'])[:24].ljust(24)+" 著:"+au[:14].ljust(14)+" 巻:"+str(nums), flush=True)
    print(f'\n→ .cache/genre-rakuten/sef-b-targets.json',flush=True)

if __name__=='__main__': main()
