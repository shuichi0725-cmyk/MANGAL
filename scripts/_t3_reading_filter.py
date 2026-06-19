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
def _strip(s):
    s=unicodedata.normalize('NFKC',str(s or ''))
    return re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
def kata(s):
    s=_strip(s); s=re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
    return re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+♡♥△▲★☆〜]','',s).lower()
def kanji(s):  # 漢字のみ抽出(列一致で同一作判定)
    return ''.join(re.findall(r'[一-龯々〆ヶ]', _strip(s)))
def alnum(s):  # 英数字のみ(I''s/COBRA/Mär等の同一作判定)
    return ''.join(re.findall(r'[a-z0-9]', _strip(s).lower()))

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
        meta[slug]={'kana':kata(d.get('title_kana')),'title':d.get('title') or '',
                    'kanji':kanji(d.get('title')),'alnum':alnum(d.get('title')),
                    'en_alnum':alnum((d.get('alternative_titles') or {}).get('en','')),
                    'en_kata':kata((d.get('alternative_titles') or {}).get('en',''))}
    real=[]; fp=[]
    for x in rows:
        m=meta.get(x[0]); rk_kata=kata(x[5]); rk_kanji=kanji(x[5]); rk_alnum=alnum(x[5])
        same=False
        if m:
            if m['kana'] and rk_kata and m['kana']==rk_kata: same=True              # フリガナ一致
            elif len(m['kanji'])>=2 and m['kanji']==rk_kanji: same=True               # 漢字列一致(2字以上。銀牙伝説Weed↔ウィード。1字共通[姫]の誤一致を回避)
            elif m['alnum'] and rk_alnum and len(m['alnum'])>=2 and m['alnum']==rk_alnum: same=True  # 英数一致(I''s/COBRA/Mär)
            elif m['en_kata'] and rk_kata and m['en_kata']==rk_kata: same=True        # 英題のカナ一致
            elif m['en_alnum'] and rk_alnum and len(m['en_alnum'])>=2 and m['en_alnum']==rk_alnum: same=True
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
