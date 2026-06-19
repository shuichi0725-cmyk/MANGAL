#!/usr/bin/env python3
"""
slug≠題名(フォルダ名と題が全然違う)洗い出し。slugは title_kana のローマ字のはず。
romaji(title_kana) と slug(ハイフン除去) の文字重なりが低い=不整合。
r-<isbn>/数字slug/kana不整合(title≠title_kana) も別途flag。
出力: data/seeds/slug-title-mismatch.tsv
"""
import sys,glob,os,re,unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
KMAP={'キャ':'kya','キュ':'kyu','キョ':'kyo','シャ':'sha','シュ':'shu','ショ':'sho','チャ':'cha','チュ':'chu','チョ':'cho','ニャ':'nya','ニュ':'nyu','ニョ':'nyo','ヒャ':'hya','ヒュ':'hyu','ヒョ':'hyo','ミャ':'mya','ミュ':'myu','ミョ':'myo','リャ':'rya','リュ':'ryu','リョ':'ryo','ギャ':'gya','ギュ':'gyu','ギョ':'gyo','ジャ':'ja','ジュ':'ju','ジョ':'jo','ビャ':'bya','ビュ':'byu','ビョ':'byo','ピャ':'pya','ピュ':'pyu','ピョ':'pyo'}
S={'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho','マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo','ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo','ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do','バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po','ァ':'a','ィ':'i','ゥ':'u','ェ':'e','ォ':'o','ー':'','・':'','　':'',' ':''}
def romaji(kana):
    kana=hk(unicodedata.normalize('NFKC',str(kana or ''))); out=[];i=0
    while i<len(kana):
        c2=kana[i:i+2]
        if c2 in KMAP: out.append(KMAP[c2]); i+=2; continue
        ch=kana[i]
        if ch=='ッ': i+=1; continue
        if ch in S: out.append(S[ch])
        elif re.match(r'[a-zA-Z0-9]',ch): out.append(ch.lower())
        i+=1
    return ''.join(out)
def kanji(s): return ''.join(re.findall(r'[一-龯々]',str(s or '')))
def charset(s): return set(re.sub(r'[^a-z0-9]','',s.lower()))
def overlap(a,b):
    if not a or not b: return 0.0
    ca,cb=charset(a),charset(b)
    if not ca or not cb: return 0.0
    return len(ca&cb)/max(1,min(len(ca),len(cb)))

def main():
    rows=[]
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%15000==0 and i: print(f'  ...{i}',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        slug=d.get('slug') or ''; title=str(d.get('title') or ''); tk=str(d.get('title_kana') or '')
        sl=slug.replace('-','')
        exp=romaji(tk) or romaji(title)
        ov=overlap(exp,sl)
        kana_kanji = bool(kanji(tk))             # title_kanaに漢字=ヨミ不整合
        title_vs_kana_kanji = kanji(title) and kanji(tk) and kanji(title)!=kanji(tk)  # title≠kanaの漢字違い
        flag=''
        if re.fullmatch(r'r-\d+',slug): flag='r-ISBN(placeholder)'
        elif kana_kanji and ov<0.5: flag='kana漢字残り(slug根拠不正)'
        elif title_vs_kana_kanji: flag='title≠kana(別作の読み)'
        elif ov<0.34 and len(sl)>=3 and exp: flag='slug≠題読み(低一致)'
        if flag:
            rows.append([slug,title[:20],tk[:16],exp[:16],round(ov,2),flag])
    rows.sort(key=lambda r:(r[5],r[4]))
    import csv
    with open(ROOT/'data'/'seeds'/'slug-title-mismatch.tsv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','title_kana','期待romaji','一致度','flag'])
        for r in rows: w.writerow(r)
    from collections import Counter
    print(f'\nslug≠題名 候補: {len(rows)}')
    print('内訳:',dict(Counter(r[5] for r in rows)))
    print('-- サンプル --')
    for r in rows[:25]: print(f'  {r[0][:20]:20s}「{r[1][:14]}」kana={r[2][:12]} exp={r[3][:12]} 一致{r[4]} [{r[5]}]')

if __name__=='__main__': main()
