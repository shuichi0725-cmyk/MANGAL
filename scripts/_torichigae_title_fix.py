#!/usr/bin/env python3
"""
NDL是正の補正: 同一作(楽天core==NDL core)は楽天題(整形きれい)に戻す。
別作(楽天が誤り=core不一致)の時だけNDL題を採用(整形クリーン)。
changelog(old=楽天 / ndl)を使用。 本番+preview両方。
"""
import sys,re,json,unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def stripall(s):  # 比較用: 巻番号/記号/空白/大小すべて除去
    s=zen(unicodedata.normalize('NFKC',str(s or ''))); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'(vol\.?|chapter|第)','',s,flags=re.I)
    return re.sub(r'[\s　・:：.,。．\-ー~〜!！?？&＆/+\d]','',s).lower()
def clean(t):  # NDL題の整形(末尾の vol./巻番号/記号のみ除去。 副題[:SIDE-B]は保持=情報喪失回避)
    t=zen(unicodedata.normalize('NFKC',str(t or ''))).strip()
    for _ in range(4):
        t=re.sub(r'\s*(vol\.?|chapter\b.*|第?\s*\d+\s*巻?|[.。、，]+)\s*$','',t,flags=re.I).strip()
    t=re.sub(r'^[（(\[]|[）)\]]$','',t).strip()   # 片側だけの括弧除去(三國志))
    return t.strip(' .。、，-―ー　') or t

def main():
    cl={}
    for l in open(ROOT/'data'/'seeds'/'torichigae-ndlverify-changelog.jsonl',encoding='utf-8'):
        r=json.loads(l); cl[r['new_slug']]=r   # new_slug は是正後slug(rename無=元と同じ)
    reverted=0; keptndl=0
    for slug,r in cl.items():
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        old=r['old_title']; ndl=r['ndl_title']
        if stripall(old)==stripall(ndl) or (stripall(old) and stripall(old) in stripall(ndl)) or (stripall(ndl) and stripall(ndl) in stripall(old)):
            newt=clean(old) or old   # 同一作=楽天題を整形して採用
            reverted+=1
        else:
            newt=clean(ndl) or ndl   # 別作=NDL題(楽天が誤り)
            keptndl+=1
        if newt and newt!=d.get('title'):
            d['title']=newt
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists():
                    dd=yaml.load(f2.read_text(encoding='utf-8'),Loader=L); dd['title']=newt
                    f2.write_text(yaml.dump(dd,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
    print(f'補正完了: 同一作=楽天題に整形復帰 {reverted} / 別作=NDL題採用 {keptndl}')
    # 確認サンプル
    import random
    for slug in list(cl)[:12]:
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if fp.exists():
            d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
            ti=str(d.get('title'))[:22]
            print(f'  {slug[:20]:20s}「{ti}」')

if __name__=='__main__': main()
