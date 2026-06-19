#!/usr/bin/env python3
"""
A3-1 publisher解決: 新作の(unknown)を楽天publisherName→publishers.yml(name→key 厳密一致)で解決。
A3-2 genres: 楽天caption有時のみ master32からkeyword分類(genres_rakuten:true)。caption無は暫定維持(嘘付けない)。
だろう運転禁止=name厳密一致のみ。 dry-run/--apply。
"""
import sys,json,unicodedata,re
from pathlib import Path
from collections import Counter,defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
APPLY='--apply' in sys.argv
def nrm(s): return unicodedata.normalize('NFKC',str(s or '')).strip()
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
# publishers.yml name->key
py=yaml.safe_load((ROOT/'data'/'publishers.yml').read_text(encoding='utf-8')) or {}
NAME2KEY={}
for k,v in py.items():
    nm=nrm(v.get('name') if isinstance(v,dict) else v)
    if nm: NAME2KEY[nm]=k
GK=[('isekai',['異世界','転生','転移','悪役令嬢']),('romcom',['ラブコメ']),('romance',['恋','ラブストーリ','結婚','婚約','溺愛','片思い','純愛']),('fantasy',['ファンタジー','魔法','魔王','勇者','ドラゴン','冒険者']),('action',['バトル','戦い','格闘','アクション','戦闘']),('baseball',['野球','甲子園']),('soccer',['サッカー']),('sports',['スポーツ','部活']),('horror',['ホラー','恐怖','怪談','戦慄']),('mystery',['推理','探偵','殺人','事件簿']),('gag',['ギャグ']),('comedy',['コメディ','爆笑']),('school',['学園','高校','生徒会','クラスメイト']),('historical',['歴史','戦国','幕末','武将']),('samurai',['侍','剣豪','時代劇']),('sci-fi',['sf','宇宙','ロボット','人工知能']),('gourmet',['料理','グルメ','美食','食堂']),('slice-of-life',['日常','ほのぼの']),('drama',['ドラマ','人生','感動','青春']),('bl',['ボーイズラブ']),('supernatural',['妖怪','幽霊','超能力','あやかし']),('mahou-shoujo',['魔法少女']),('mecha',['ロボット','メカ']),('war',['戦争','軍']),('music',['音楽','バンド','ピアノ'])]
def guess(cap):
    c=nrm(cap).lower(); g=[]
    for key,kws in GK:
        if any(k.lower() in c for k in kws): g.append(key)
    out=[]
    for x in g:
        if x not in out: out.append(x)
    return out[:4]

def main():
    rk={}
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        it=o.get('item') or {}
        if ib and it: rk[ib]={'pub':nrm(it.get('publisherName')),'cap':it.get('itemCaption','') or ''}
    slugs=[]; seen=set()
    for l in open(ROOT/'data'/'seeds'/'torichigae-ndlverify-changelog.jsonl',encoding='utf-8'):
        s=json.loads(l)['new_slug']
        if s not in seen and (ROOT/'data'/'manga.v2'/f'{s}.yml').exists(): seen.add(s); slugs.append(s)
    pub_fixed=gen_fixed=0; unresolved=Counter()
    for s in slugs:
        fp=ROOT/'data'/'manga.v2'/f'{s}.yml'
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        isbns=[to13(v.get('isbn13')) for e in d.get('editions',[]) for v in e.get('volumes',[]) if to13(v.get('isbn13'))]
        # publisher
        keys=[]
        for ib in isbns:
            pn=rk.get(ib,{}).get('pub','')
            if pn in NAME2KEY: keys.append(NAME2KEY[pn])
            elif pn: unresolved[pn]+=1
        chg=False
        if keys:
            from collections import Counter as C
            main_k=C(keys).most_common(1)[0][0]; allk=sorted(set(keys))
            if d.get('publisher')!=main_k:
                d['publisher']=main_k; d['publishers']=allk
                for e in d.get('editions',[]): e['publisher']=main_k
                chg=True; pub_fixed+=1
        # genres (caption有時のみ)
        caps=' '.join(rk.get(ib,{}).get('cap','') for ib in isbns)
        if caps.strip():
            g=guess(caps)
            if g and g!=d.get('genres'):
                d['genres']=g; d.pop('genres_provisional',None); d['genres_rakuten']=True; chg=True; gen_fixed+=1
        if chg and APPLY:
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{s}.yml'
                if f2.exists(): f2.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
    print(f'publisher解決 {pub_fixed} / genres(楽天caption)更新 {gen_fixed} / 対象 {len(slugs)}')
    print('未解決publisher(publishers.yml未登録・上位):')
    for n,c in unresolved.most_common(12): print(f'  {n}: {c}')
    if not APPLY: print('\n(dry-run。 --applyで適用)')

if __name__=='__main__': main()
