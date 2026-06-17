#!/usr/bin/env python3
"""
特装版混入 修正(a)= 種1だけで直せる分の修正データ生成。

対象: 本番DB standard版に入っている「おまけ特装/限定」ISBN のうち、
      種1(MADB schema:version)で特装版と判明し、かつ **種1に同巻・version無しの通常版兄弟** がある巻。
方針(案B): 通常版を主(isbn/cover/date 差替)、特装版は variant として併存(捨てない)。

種1=版名の権威。書影=既存の楽天収穫(.cache/rakuten-isbn.jsonl)から取得(新規API呼ばない)。
出力(git追跡): data/seeds/special-edition-fix.yml  + サマリ .cache/genre-rakuten/sef-summary.json
"""
import json,re,sqlite3,time
from pathlib import Path
from collections import defaultdict,Counter

import sys
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml

def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
        return None
    return v
def ym(s):
    m=re.match(r'(\d{4})(?:-(\d{2}))?',str(s or ''))
    return (int(m.group(1))*12+(int(m.group(2)) if m and m.group(2) else 6)) if m else None
def yen(s):
    m=re.search(r'(\d[\d,]*)',str(s or '')); return int(m.group(1).replace(',','')) if m else None
def vnorm(v):
    try: return str(int(float(v)))
    except: return str(v or '')
def to13(s):
    s=str(s or '').replace('-','').strip()
    if len(s)==13 and s.isdigit(): return s
    if len(s)==10:
        c='978'+s[:9]
        try: tot=sum((1 if i%2==0 else 3)*int(d) for i,d in enumerate(c))
        except: return None
        return c+str((10-tot%10)%10)
    return None

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
        rec={'ver':(first(r.get('schema:version')) or '').strip(),'date':first(r.get('schema:datePublished')),
             'dm':ym(first(r.get('schema:datePublished'))),'price':yen(first(r.get('schema:price'))),
             'isbn':isbn,'key':(str(cr),str(nm),vn)}
        recs[rec['key']].append(rec)
        if isbn: isbn2rec[isbn]=rec
    print(f'[{time.time()-t0:.0f}s] 種1 index',flush=True)

    # 楽天収穫: isbn -> cover(noimage除外)
    cover={}
    with open('.cache/rakuten-isbn.jsonl',encoding='utf-8') as f:
        for line in f:
            try: o=json.loads(line)
            except: continue
            it=o.get('item') or {}
            url=it.get('largeImageUrl') or it.get('mediumImageUrl') or ''
            if not url or 'noimage' in url: continue
            i=to13(o.get('isbn') or it.get('isbn'))
            if i: cover[i]=url.split('?')[0]+'?_ex=200x200'
    print(f'[{time.time()-t0:.0f}s] 楽天書影 {len(cover):,}',flush=True)

    # DB standard ISBN
    c=sqlite3.connect('.cache/db-v2.sqlite')
    std=set()
    for (i,) in c.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.type='standard' AND v.isbn13 IS NOT NULL"):
        x=to13(i)
        if x: std.add(x)

    corr=[]; st=Counter(); no_norm_cover=0
    for i in std:
        r=isbn2rec.get(i)
        if not r or not is_omake(r['ver']): continue
        sibs=[x for x in recs[r['key']] if not x['ver'] and x['isbn'] and x['isbn']!=i]
        if not sibs: continue   # (b) は対象外
        # 通常版兄弟 = special と発売月が近い → 書影あり を優先
        def score(x):
            gap=abs((x['dm'] or 0)-(r['dm'] or 0))
            return (gap, 0 if x['isbn'] in cover else 1)
        sib=sorted(sibs,key=score)[0]
        nc=cover.get(sib['isbn'])
        if not nc: no_norm_cover+=1
        corr.append({
            'special_isbn': i,
            'normal_isbn': sib['isbn'],
            'normal_cover': nc,
            'normal_date': (sib['date'] if re.match(r'^\d{4}(-\d{2})?$',str(sib['date'] or '')) else None),
            'variant': {'label': r['ver'], 'isbn13': i,
                        'cover_url': cover.get(i), 'price': r['price']},
        })
        st[r['ver']]+=1

    corr.sort(key=lambda x:x['special_isbn'])
    hdr=("# 特装版混入 修正(a)= 種1で通常版兄弟がある巻。 通常版を主に差替+特装をvariant併存(案B)。\n"
         "# 生成: scripts/_special_edition_fix_gen.py / 適用: _special_edition_fix_apply.py。 種1=版名権威・書影=楽天収穫。\n")
    (ROOT/'data'/'seeds'/'special-edition-fix.yml').write_text(
        hdr+yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False), encoding='utf-8')
    (ROOT/'.cache'/'genre-rakuten'/'sef-summary.json').write_text(
        json.dumps({'total':len(corr),'normal_cover_missing':no_norm_cover,'by_version':dict(st.most_common())},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'\n修正(a)件数: {len(corr):,}  / 通常版書影が楽天収穫に無い: {no_norm_cover:,}',flush=True)
    print('版名内訳(上位12):',flush=True)
    for v,n in st.most_common(12): print(f'   {n:5d} {v[:36]}',flush=True)
    print('サンプル:',flush=True)
    for x in corr[:6]:
        print(f"   {x['special_isbn']}[{x['variant']['label']}] → 通常{x['normal_isbn']} cover={'有' if x['normal_cover'] else '無'}",flush=True)
    print(f'\nseed → data/seeds/special-edition-fix.yml',flush=True)

if __name__=='__main__': main()
