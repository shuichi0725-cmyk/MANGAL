#!/usr/bin/env python3
"""
A1: 139新作をNDL(ISBN権威)で題・kana・slug再検証/是正(楽天誤題の修正)。
各作の先頭/末尾巻ISBNをNDL照会:
- 題が揃う(同一シリーズ) → NDL正題に是正 + kana(NDLヨミ) + slug再生成(rename)
- 題が食い違う(複数作混在) → flag(routeC・手動)
- 非漫画(目録/事典/カタログ/総目録) → 削除(scope外)
backup+changelog・可逆。
"""
import sys,re,json,time,shutil,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def lnm(t): return t.split('}')[-1]
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def stripvol(s):
    s=zen(unicodedata.normalize('NFKC',str(s or ''))); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'\s*[:：].*$','',s)   # 副題除去
    s=re.sub(r'\s*(第)?\d+\s*(巻|集)?\s*$','',s); return s.strip()
def lcp(a,b):
    a=a or ''; b=b or ''; n=0
    while n<len(a) and n<len(b) and a[n]==b[n]: n+=1
    return a[:n]
NONMANGA=['総目録','目録','事典','大事典','カタログ','解説総','名鑑','便覧','年鑑','図録']
# kana→romaji
KMAP={'キャ':'kya','キュ':'kyu','キョ':'kyo','シャ':'sha','シュ':'shu','ショ':'sho','チャ':'cha','チュ':'chu','チョ':'cho','ニャ':'nya','ニュ':'nyu','ニョ':'nyo','ヒャ':'hya','ヒュ':'hyu','ヒョ':'hyo','ミャ':'mya','ミュ':'myu','ミョ':'myo','リャ':'rya','リュ':'ryu','リョ':'ryo','ギャ':'gya','ギュ':'gyu','ギョ':'gyo','ジャ':'ja','ジュ':'ju','ジョ':'jo','ビャ':'bya','ビュ':'byu','ビョ':'byo','ピャ':'pya','ピュ':'pyu','ピョ':'pyo'}
S={'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o','カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko','サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so','タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to','ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no','ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho','マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo','ヤ':'ya','ユ':'yu','ヨ':'yo','ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro','ワ':'wa','ヲ':'o','ン':'n','ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go','ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo','ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do','バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo','パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po','ァ':'a','ィ':'i','ゥ':'u','ェ':'e','ォ':'o','ー':'','・':' ','　':' '}
def romaji(kana):
    kana=hk(unicodedata.normalize('NFKC',str(kana or ''))); out=[];i=0
    while i<len(kana):
        c2=kana[i:i+2]
        if c2 in KMAP: out.append(KMAP[c2]); i+=2; continue
        ch=kana[i]
        if ch=='ッ': out.append((KMAP.get(kana[i+1:i+3]) or S.get(kana[i+1:i+2],''))[:1]); i+=1; continue
        if ch in S: out.append(S[ch])
        elif re.match(r'[a-zA-Z0-9]',ch): out.append(ch.lower())
        i+=1
    return re.sub(r'\s+',' ',''.join(out)).strip()
def slugify(kana,title,isbn=''):
    base=romaji(kana) or romaji(title); s=re.sub(r'[^a-z0-9 ]','',base.lower()); s=re.sub(r'\s+','-',s.strip())
    if len(s.replace('-',''))<3: s='r-'+(isbn[-7:] if isbn else 'x')
    return s
def ndl(isbn):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'1','query':f'isbn="{isbn}"'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'M/0.1'}),timeout=20).read(); break
        except Exception:
            if at<2: time.sleep(1.5); continue
            return {}
    try: root=ET.fromstring(b)
    except: return {}
    r={}
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        kids=list(rd); it=list(rd.iter()) if kids else (list(ET.fromstring(rd.text).iter()) if rd.text and '<' in rd.text else [])
        for el in it:
            k=lnm(el.tag); tx=(el.text or '').strip()
            if k=='title' and tx and 'title' not in r: r['title']=tx
            if k=='titleTranscription' and tx and 'yomi' not in r: r['yomi']=tx
        break
    return r

def main():
    rows=[json.loads(l) for l in open(ROOT/'data'/'seeds'/'torichigae-created.jsonl',encoding='utf-8')]
    print(f'NDL検証 {len(rows)} 新作',flush=True)
    bak=ROOT/'.cache'/f'ndlverify-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    lf=(ROOT/'data'/'seeds'/'torichigae-ndlverify-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    existing=set(p.stem for p in (ROOT/'data'/'manga.v2').glob('*.yml'))
    fixed=0; removed=[]; flagged=[]; renamed=0
    for i,r in enumerate(rows,1):
        slug=r['new_slug']; fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        vols=d['editions'][0]['volumes']; isbns=[str(v.get('isbn13')) for v in vols if v.get('isbn13')]
        if not isbns: continue
        n1=ndl(isbns[0]); time.sleep(1.0)
        nN=ndl(isbns[-1]) if len(isbns)>1 else n1; time.sleep(1.0 if len(isbns)>1 else 0)
        t1=stripvol(n1.get('title','')); tN=stripvol(nN.get('title',''))
        if not t1 and not tN: continue   # NDL不在=触らない
        series=lcp(t1,tN) if (t1 and tN) else (t1 or tN)
        # 複数作混在 = 先頭末尾の題がほぼ無共通
        if t1 and tN and len(series)<2 and len(isbns)>1:
            flagged.append((slug,t1,tN)); continue
        if any(k in series for k in NONMANGA):
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.unlink()
            removed.append((slug,series)); continue
        newtitle=series or d['title']
        yomi=stripvol(n1.get('yomi','')) or stripvol(nN.get('yomi',''))
        changed = newtitle!=d.get('title')
        d['title']=newtitle
        if yomi: d['title_kana']=hk(yomi); d['title_romaji']=romaji(yomi)
        # slug再生成(ヨミ有時のみ・rename)
        newslug=slug
        if yomi:
            cand=slugify(yomi,newtitle,isbns[0])
            if cand!=slug and not cand.startswith('r-') and cand not in existing:
                newslug=cand; d['slug']=cand
        for base in ('data/manga.v2','.preview-data/manga'):
            f2=ROOT/base/f'{slug}.yml'
            if not f2.exists(): continue
            shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml'))
            out=ROOT/base/f'{newslug}.yml'
            out.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            if newslug!=slug: f2.unlink()
        if newslug!=slug: existing.add(newslug); renamed+=1
        if changed or yomi: fixed+=1
        lf.write(json.dumps({'old_slug':slug,'new_slug':newslug,'old_title':r['title'],'ndl_title':newtitle,'at':st},ensure_ascii=False)+'\n')
        if i%30==0: print(f'  {i}/{len(rows)} fixed{fixed} renamed{renamed} removed{len(removed)} flag{len(flagged)}',flush=True)
    lf.close()
    (ROOT/'data'/'seeds'/'torichigae-ndl-multiwork.tsv').write_text('\n'.join('\t'.join(x) for x in flagged),encoding='utf-8')
    print(f'\nNDL検証完了: 是正{fixed} / slug rename{renamed} / 非漫画削除{len(removed)} / 複数作混在flag{len(flagged)}')
    print('削除(非漫画):',[s for s,_ in removed][:10])
    print('混在flag:',[s for s,_,_ in flagged][:10])

if __name__=='__main__': main()
