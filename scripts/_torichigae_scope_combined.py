#!/usr/bin/env python3
"""
scope OR判定: 楽天booksGenre(001001=コミック) OR NDL NDC(726=漫画) のどちらかが漫画なら漫画。
両方が分類を持ち両方とも非漫画 → 非漫画(削除候補)。 どちらも分類無 → uncertain(保持)。
ページ数/出版社も併記(整合確認)。 既存130新作 + 既削除5(再評価)。 dry-run(既定)/--apply。
出力: data/seeds/torichigae-scope-combined.tsv
"""
import sys,csv,re,json,time,shutil,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
APPLY='--apply' in sys.argv
def lnm(t): return t.split('}')[-1]
def ndl_ndc(isbn):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'1','query':f'isbn="{isbn}"'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'M/0.1'}),timeout=20).read(); break
        except Exception:
            if at<2: time.sleep(1.5); continue
            return None,None
    try: root=ET.fromstring(b)
    except: return None,None
    has=False; subs=[]
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        has=True; kids=list(rd); it=list(rd.iter()) if kids else (list(ET.fromstring(rd.text).iter()) if rd.text and '<' in rd.text else [])
        for el in it:
            if lnm(el.tag)=='subject' and (el.text or '').strip(): subs.append(el.text.strip())
        break
    if not has: return False,None
    ndcs=[s for s in subs if re.match(r'^\d',s)]
    return True, ndcs   # (NDLにある, NDCリスト or [])

def main():
    rk={}
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=str(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        it=o.get('item') or {}
        if it: rk[ib]={'g':it.get('booksGenreId',''),'pg':it.get('size',''),'pub':it.get('publisherName','')}
    slugs=[]; seen=set()
    for l in open(ROOT/'data'/'seeds'/'torichigae-ndlverify-changelog.jsonl',encoding='utf-8'):
        s=json.loads(l)['new_slug']
        if s not in seen and (ROOT/'data'/'manga.v2'/f'{s}.yml').exists(): seen.add(s); slugs.append(s)
    print(f'scope OR判定 {len(slugs)}',flush=True)
    rows=[]; mc=nm=unc=0
    for i,s in enumerate(slugs,1):
        d=yaml.load((ROOT/'data'/'manga.v2'/f'{s}.yml').read_text(encoding='utf-8'),Loader=L)
        isbns=[str(v.get('isbn13')) for e in d.get('editions',[]) for v in e.get('volumes',[]) if v.get('isbn13')]
        # 楽天: いずれかの巻が001001
        rk_comic=any(rk.get(ib,{}).get('g','').startswith('001001') for ib in isbns)
        rk_anyg=any(rk.get(ib,{}).get('g','') for ib in isbns)
        # NDL NDC: 先頭3巻
        ndc_all=[]; ndl_has=False
        for ib in isbns[:3]:
            h,nd=ndl_ndc(ib); time.sleep(1.0)
            if h: ndl_has=True
            if nd: ndc_all+=nd
            if any(x.startswith('726') for x in (nd or [])): break
        ndc726=any(x.startswith('726') for x in ndc_all)
        ndc_nonmanga = bool(ndc_all) and not ndc726
        # OR判定
        if rk_comic or ndc726: v='漫画'; mc+=1
        elif ndc_nonmanga and not rk_comic: v='非漫画(削除候補)'; nm+=1
        else: v='不明(保持)'; unc+=1
        pg=rk.get(isbns[0],{}).get('pg','') if isbns else ''
        rows.append([s,d.get('title','')[:18],('楽天C' if rk_comic else ('楽天:'+(next((rk[ib]['g'] for ib in isbns if rk.get(ib,{}).get('g')),'')[:9] or '無'))),(';'.join(ndc_all)[:14] or ('NDL有NDC空' if ndl_has else 'NDL無')),pg,v])
        if i%30==0: print(f'  {i}/{len(slugs)} 漫画{mc} 非{nm} 不明{unc}',flush=True)
    rows.sort(key=lambda r:(r[5],r[0]))
    with open(ROOT/'data'/'seeds'/'torichigae-scope-combined.tsv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','title','楽天','NDC','ページ','OR判定'])
        for r in rows: w.writerow(r)
    print(f'\nOR判定: 漫画{mc} / 非漫画(削除候補){nm} / 不明保持{unc}')
    print('-- 非漫画(削除候補) --')
    for r in rows:
        if '非漫画' in r[5]: print(f'  {r[0][:18]:18s}「{r[1][:14]}」楽天[{r[2]}] NDC[{r[3]}]')
    if APPLY:
        bak=ROOT/'.cache'/f'scopeor-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
        for r in rows:
            if '非漫画' in r[5]:
                for base in ('data/manga.v2','.preview-data/manga'):
                    f2=ROOT/base/f'{r[0]}.yml'
                    if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+r[0]+'.yml')); f2.unlink()
        print(f'削除適用 backup={bak}')

if __name__=='__main__': main()
