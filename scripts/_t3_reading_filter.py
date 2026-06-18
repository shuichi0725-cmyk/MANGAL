#!/usr/bin/env python3
"""
T3偽陽性除去(台帳クリーニング・本番不変)。
我々のtitle_kana(フリガナ)と楽天題(カナ正規化)が exact一致=同一作の表記違い(19<Nineteen>↔ナインティーン型)
→ T3から除外(真の誤りでない)。 続編誤判定を避けるため exact一致のみ(部分一致は使わない)。
出力: audit-T3-real.tsv(真の誤り) / audit-T3-falsepos-reading.tsv(除外=同一作)
"""
import csv,re,unicodedata,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def kata(s):
    s=unicodedata.normalize('NFKC',str(s or ''))
    s=re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
    s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    return re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+♡♥△▲★☆〜]','',s).lower()

def main():
    rows=[]
    with open(ROOT/'data'/'seeds'/'audit-T3-wrongproduct.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); hdr=next(r); rows=[x for x in r]
    # slug -> title_kana/romaji
    meta={}
    for slug in set(x[0] for x in rows):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        meta[slug]={'kana':kata(d.get('title_kana')),'romaji':re.sub(r'[\s\-]','',str(d.get('title_romaji') or '')).lower(),
                    'en':kata((d.get('alternative_titles') or {}).get('en',''))}
    real=[]; fp=[]
    for x in rows:
        m=meta.get(x[0]); rk=kata(x[5])
        same=False
        if m and rk:
            if m['kana'] and m['kana']==rk: same=True            # フリガナ exact
            elif m['en'] and m['en']==rk: same=True               # 英題カナ exact(稀)
        (fp if same else real).append(x)
    for name,data in (('audit-T3-real',real),('audit-T3-falsepos-reading',fp)):
        with open(ROOT/'data'/'seeds'/f'{name}.tsv','w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f,delimiter='\t'); w.writerow(hdr)
            for x in data: w.writerow(x)
    from collections import Counter
    print(f'T3 {len(rows)} → 真の誤り {len(real)} / 読み一致で除外(同一作) {len(fp)}')
    print(f'  除外された作品(ユニーク): {len(set(x[0] for x in fp))}')
    print('-- 除外サンプル(同一作の表記違い)--')
    seen=set()
    for x in fp:
        if x[0] in seen: continue
        seen.add(x[0]); print(f'  {x[0][:22]:22s} 我「{x[1][:14]}」= 楽天「{x[5][:16]}」')
        if len(seen)>=15: break

if __name__=='__main__': main()
