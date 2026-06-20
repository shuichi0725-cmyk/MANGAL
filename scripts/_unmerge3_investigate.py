#!/usr/bin/env python3
"""
③誤側作品が実在(別途ISBN有)か幻かを調査: 各誤側のDB著者・題で種1/楽天を全走査し、
共有(誤)ISBN以外に「その著者×その題」のISBNが存在するか=本当の持ち主のISBNを探す。
read-only。計画立案用。
"""
import sys,json,re,unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
    return v
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def naz(s): return hk(re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-0-9０-９]','',unicodedata.normalize('NFKC',str(s or '')))).lower()

# ③誤側 (slug, 期待著者list, 期待題core)
WRONG=[
 ('24colors',['千葉コズエ'],'24colors'),
 ('venus-2015',['麻生歩'],'ヴィーナス'),
 ('kurotokage-2019',['森下裕美'],'黒トカゲ'),
 ('gift-2006',['ユキヲ'],'gift'),
 ('gift-2012',['塩森恵子'],'gift'),
 ('hiyoko-brand',None,'hiyokobrand'),
 ('fire-emblem-thracia-776-2000',['日野慎之助'],'ファイアーエムブレムトラキア'),
]
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    return yaml.safe_load(fp.read_text(encoding='utf-8')) if fp.exists() else None
def main():
    # 各誤側の現ISBN(=誤共有ISBN)を集める→除外用
    badisbn=set()
    info={}
    for slug,au,tc in WRONG:
        d=load(slug); info[slug]=d
        if d:
            for e in d.get('editions',[]):
                for v in e.get('volumes',[]):
                    ib=to13(v.get('isbn13'))
                    if ib: badisbn.add(ib)
            if au is None:
                au=[a.get('name') for a in (d.get('authors') or [])]
            print(f'■{slug}「{d.get("title")}」DB著者={[a.get("name") for a in (d.get("authors") or [])]}')
    print('共有(誤)ISBN総数:',len(badisbn),'\n--- 種1/楽天で「著者×題」の本当のISBNを探索 ---')
    # 全走査
    hits={slug:[] for slug,_,_ in WRONG}
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    def check(ib,title,author,src):
        if not ib or ib in badisbn: return
        nt=naz(title); na_=naz(author)
        if not nt or not na_: return   # 空題/空著者は判定不可(誤マッチ防止)
        for slug,au,tc in WRONG:
            d=info[slug]
            aus=au or [a.get('name') for a in ((d.get('authors') if d else []) or [])]
            ta=any(naz(a) and naz(a) in na_ for a in aus) if aus else False  # 著者が記録著者に含まれる
            tt=bool(tc) and len(tc)>=2 and tc in nt                          # 題coreが記録題に含まれる
            if ta and tt: hits[slug].append((ib,title[:24],author[:14],src))
    for r in g:
        ib=to13(first(r.get('schema:isbn')))
        if ib: check(ib, first(r.get('schema:name')) or '', first(r.get('schema:creator')) or '','種1')
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        it=o.get('item') or {}
        if ib: check(ib, it.get('title',''), it.get('author',''),'楽天')
    for slug,_,_ in WRONG:
        h=hits[slug]
        print(f'\n▸{slug}: 本当のISBN候補 {len(h)}件')
        for ib,t,a,src in h[:12]: print(f'    {ib} [{src}] {t} / {a}')
        if not h: print('    → 著者×題のISBN無し=幻(phantom)か別表記。要NDL/Wiki')

if __name__=='__main__': main()
