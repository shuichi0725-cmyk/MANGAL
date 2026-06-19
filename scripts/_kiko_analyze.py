#!/usr/bin/env python3
"""
奇子型 分析器(dry・本番不変): 版内発売日ギャップ作を cm104(版オーソリティ)で判定。
- cm104に同題で複数版あり、巻の年クラスタが別版に対応 → SPLIT(別版混在=分離候補)
- cm104が単一版/年範囲を1版でカバー → LEAVE(正当な長期連載=触らない)
- cm104データ無/曖昧 → UNCERTAIN
「正しいものを出してるか」確認が主眼。 --limit N。
"""
import sys,re,json,csv
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
LIMIT=10
for a in sys.argv:
    if a.startswith('--limit='): LIMIT=int(a.split('=')[1])
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def tcore(s):
    s=zen(str(s or '')); import unicodedata; s=unicodedata.normalize('NFKC',s)
    s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s); s=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
    return hk(s)
def yr(s):
    m=re.match(r'(\d{4})',str(s or '')); return int(m.group(1)) if m else None
def f1(v):
    if isinstance(v,list): return v[0] if v else ''
    return v

def load_cm104():
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata104.json',encoding='utf-8'))
    g=g.get('@graph',g) if isinstance(g,dict) else g
    idx=defaultdict(list)
    for r in g:
        nm=f1(r.get('ma:seriesName') or r.get('schema:name') or '')
        tc=tcore(nm)
        if not tc: continue
        idx[tc].append({'brand':f1(r.get('schema:brand','')),'n':f1(r.get('schema:numberOfItems','')),
                        'pub':f1(r.get('schema:publisher','')),'yr':yr(f1(r.get('schema:datePublished','')))})
    return idx

def main():
    print('cm104 ロード...',flush=True); cm=load_cm104(); print(f'cm104 題core {len(cm):,}',flush=True)
    cands=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'edition-gap-audit.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='slug' or x[5]!='OLD_FIRST': continue
        m=re.match(r'(\d{4})',x[7]); y=int(m.group(1)) if m else 0
        if 1958<=y<=2010: cands.append(x)   # 日付ゴミ(<1955)除外
    print(f'OLD_FIRST候補(vol1 1958-2010) {len(cands)} / 試作 {LIMIT}\n',flush=True)
    for x in cands[:LIMIT]:
        slug=x[0]
        d=yaml.load((ROOT/'data'/'manga.v2'/f'{slug}.yml').read_text(encoding='utf-8'),Loader=L)
        eds=cm.get(tcore(d.get('title')),[])
        # 該当edition(flagされたtype/label)
        te=None
        for e in d.get('editions',[]):
            if e.get('type')==x[2] and (e.get('label','')==x[3]): te=e; break
        if not te: te=d['editions'][0]
        vs=sorted(te['volumes'],key=lambda v:(v.get('number') or 0))
        vol_disp=[(v.get('number'),yr(v.get('release_date')),'I' if v.get('isbn13') else '-') for v in vs]
        # 年クラスタ
        yrs=sorted(set(y for _,y,_ in vol_disp if y))
        clusters=[]; cur=[yrs[0]] if yrs else []
        for y in yrs[1:]:
            if y-cur[-1]<=4: cur.append(y)
            else: clusters.append((cur[0],cur[-1])); cur=[y]
        if cur: clusters.append((cur[0],cur[-1]))
        # 判定
        cm_yrs=[e['yr'] for e in eds if e['yr']]
        if len(eds)>=2 and len(clusters)>=2:
            verdict='SPLIT候補(cm104複数版・巻が複数年クラスタ)'
        elif len(eds)<=1 and len(clusters)>=2:
            verdict='UNCERTAIN(cm104単一/無だが巻は複数クラスタ=要確認)'
        else:
            verdict='LEAVE?(cm104単一or年連続)'
        ti=d.get('title'); au=[a.get('name') for a in d.get('authors',[])]
        edstr=' / '.join((str(e['brand'] or '?')+'['+str(e['n'])+'巻]'+(str(e['pub']).split('∥')[0].strip() if e['pub'] else '')+(('@'+str(e['yr'])) if e['yr'] else '')) for e in eds[:6])
        print('■ '+slug+' 「'+str(ti)+'」 著='+str(au))
        print('   現'+str(x[2])+'「'+str(x[3])+'」 巻(番号,年,ISBN): '+str(vol_disp))
        print('   年クラスタ: '+str(clusters))
        print('   cm104版('+str(len(eds))+'): '+edstr)
        print('   → '+verdict+'\n')

if __name__=='__main__': main()
