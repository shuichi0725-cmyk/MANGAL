#!/usr/bin/env python3
"""
本番DBの「取り違え」全体マップ(診断・本番不変)。
audit-T3-real.tsv = 我々作品が「楽天で別作のISBN」を持つ行。 これを作品単位に集約し、
何(我々slug)が 何(楽天題=真の所有作)のISBNを抱えているか、相互swap(A↔B)も検出。
出力: data/seeds/torichigae-map.tsv
"""
import csv,re,unicodedata
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent.parent
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def ncore(s):
    s=zen(str(s or '')); s=unicodedata.normalize('NFKC',s); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'[．.]\s*\d+\s*$','',s)
    return re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()

def main():
    rows=[]
    with open(ROOT/'data'/'seeds'/'audit-T3-real.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r); rows=[x for x in r]
    # 我々作品: slug -> title_core (resolve-masterから)
    slug2core={}; core2slugs=defaultdict(set); slug2title={}
    with open(ROOT/'data'/'seeds'/'resolve-master.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            slug2core[x[0]]=ncore(x[1]); slug2title[x[0]]=x[1]; core2slugs[ncore(x[1])].add(x[0])
    # 集約: 我々slug -> 抱えてる楽天題(core)別 件数
    agg=defaultdict(lambda: defaultdict(int)); rk_title_ex={}
    for x in rows:
        slug=x[0]; rk=x[5]; rc=ncore(x[5] if len(x)>5 else '')
        if not rc: continue
        agg[slug][rc]+=1; rk_title_ex[rc]=x[5]
    out=[]
    for slug,d in agg.items():
        for rc,n in d.items():
            owner_slugs=core2slugs.get(rc,set())   # その楽天題に該当する我々作品(=正所有者候補)
            # 相互swap: owner側が逆に我々slugのcoreを抱えてるか
            mutual=any(slug2core.get(slug) in agg.get(os,{}) for os in owner_slugs)
            out.append([slug,slug2title.get(slug,''),n,rk_title_ex.get(rc,'')[:26],
                        '|'.join(sorted(owner_slugs))[:40],'★相互' if mutual else ''])
    out.sort(key=lambda z:-z[2])
    p=ROOT/'data'/'seeds'/'torichigae-map.tsv'
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['我々slug','我々title','誤ISBN数','取り違え相手(楽天題)','相手の我々slug候補','相互swap'])
        for r in out: w.writerow(r)
    works=len(agg); pairs=len(out); mutual=sum(1 for r in out if r[5])
    owner_known=sum(1 for r in out if r[4])
    print('=== 取り違えマップ ===')
    print(f'影響作品(我々slug): {works:,} / 取り違えペア(slug×楽天題): {pairs:,}')
    print(f'  うち相手が我々DB内に特定: {owner_known:,} / 相互swap(A↔B): {mutual:,}')
    print(f'→ {p}')
    print('-- 多い順サンプル --')
    for r in out[:18]:
        print(f'  {r[0][:22]:22s}「{str(r[1])[:12]}」 {r[2]:>2}件 → 楽天「{r[3][:18]}」 相手slug[{r[4][:24]}] {r[5]}')

if __name__=='__main__': main()
