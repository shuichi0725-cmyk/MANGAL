#!/usr/bin/env python3
"""
表ベース: slug × title_kana チェック(高速=各ymlの先頭数行だけ読む)。
索引 data/seeds/slug-kana-index.tsv (slug,title,title_kana,romaji,一致度) を生成・再利用。
slug ≠ romaji(title_kana) = フォルダ名が読みと不一致 を flag。
"""
import sys,re,unicodedata,csv
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
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
        elif re.match(r'[a-z0-9]',ch.lower()): out.append(ch.lower())
        i+=1
    return ''.join(out)
def kanji(s): return ''.join(re.findall(r'[一-龯々]',str(s or '')))
def cs(s): return set(re.sub(r'[^a-z0-9]','',str(s).lower()))
def ov(a,b):
    ca,cb=cs(a),cs(b)
    if not ca or not cb: return 0.0
    return len(ca&cb)/min(len(ca),len(cb))
def field(lines,key):
    for ln in lines:
        m=re.match(rf'^{key}:\s*(.*)$',ln)
        if m: return m.group(1).strip().strip('\'"')
    return ''

def main():
    rows=[]
    files=sorted((ROOT/'data'/'manga.v2').glob('*.yml'))
    for i,fp in enumerate(files):
        if i%20000==0 and i: print(f'  ...{i}',flush=True)
        try:
            with fp.open(encoding='utf-8') as f:
                head=[next(f) for _ in range(8)]
        except StopIteration:
            head=open(fp,encoding='utf-8').read().splitlines()
        except: continue
        slug=field(head,'slug') or fp.stem
        title=field(head,'title'); tk=field(head,'title_kana')
        rom=romaji(tk); o=round(ov(rom,slug.replace('-','')),2)
        rows.append([slug,title,tk,rom,o,'漢字残' if kanji(tk) else ''])
    out=ROOT/'data'/'seeds'/'slug-kana-index.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','title_kana','romaji(kana)','slug一致度','flag'])
        for r in rows: w.writerow(r)
    # mismatch抽出(一致度低 or 漢字残)
    mis=[r for r in rows if (r[4]<0.34 and len(r[0].replace('-',''))>=3) or r[5]=='漢字残']
    mis.sort(key=lambda r:r[4])
    mout=ROOT/'data'/'seeds'/'slug-kana-mismatch.tsv'
    with open(mout,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','title_kana','romaji(kana)','slug一致度','flag'])
        for r in mis: w.writerow(r)
    print(f'\n索引 {len(rows):,}作 → {out}')
    print(f'slug≠title_kana読み(一致度<0.34 or 漢字残): {len(mis):,} → {mout}')
    print('-- 不一致サンプル --')
    for r in mis[:22]: print(f'  {r[0][:24]:24s}「{str(r[1])[:14]}」kana={str(r[2])[:12]} rom={r[3][:12]} 一致{r[4]} {r[5]}')

if __name__=='__main__': main()
