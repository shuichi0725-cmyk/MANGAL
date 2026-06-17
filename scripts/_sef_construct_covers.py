#!/usr/bin/env python3
"""
保留分(通常版書影が楽天検索で取れなかった分)を、楽天画像CDNの**構築URL**で充填。
在庫切れ/絶版でも画像はCDNに残ることが多い: cabinet/<isbn下4桁>/<isbn>.jpg(suffix違いも試す)。
HTTP検証(200+image+サイズ>2KB)で実在確認したものだけ normal_cover に入れる。
"""
import json,urllib.request,urllib.error,time,sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml

def verify(url):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        r=urllib.request.urlopen(req,timeout=12); data=r.read()
        ct=r.headers.get('Content-Type','')
        if 'image' in ct and len(data)>2000: return True
    except Exception: pass
    return False

def cover_for(isbn):
    last4=isbn[-4:]
    base=f'https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{last4}/{isbn}'
    for suf in ('.jpg','_1_2.jpg','_1_4.jpg'):
        u=base+suf
        if verify(u+'?_ex=200x200'): return u+'?_ex=200x200'
    return None

def main():
    fp=ROOT/'data'/'seeds'/'special-edition-fix.yml'
    raw=fp.read_text(encoding='utf-8')
    hdr='\n'.join(l for l in raw.splitlines() if l.startswith('#'))
    doc=yaml.safe_load(raw); corr=doc['corrections']
    todo=[x for x in corr if not x.get('normal_cover')]
    print(f'構築URL検証: {len(todo)} 件',flush=True)
    got=0
    for n,x in enumerate(todo,1):
        cv=cover_for(x['normal_isbn'])
        if cv: x['normal_cover']=cv; got+=1
        if n%50==0: print(f'  {n}/{len(todo)} (取得 {got})',flush=True)
        time.sleep(0.05)
    fp.write_text(hdr+'\n'+yaml.dump({'corrections':corr},allow_unicode=True,sort_keys=False),encoding='utf-8')
    still=sum(1 for x in corr if not x.get('normal_cover'))
    print(f'\n構築URLで充填 {got} 件 / なお書影無し {still} 件',flush=True)

if __name__=='__main__': main()
