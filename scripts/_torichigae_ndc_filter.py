#!/usr/bin/env python3
"""
A1スコープ精緻化: 139新作をNDL NDC(subject=726.x=漫画)で権威判定。
- 726系=漫画 → keep
- NDC有るが非726 → 非漫画 → 削除(scope外)
- NDC無し → 不明 → 保持(誤除外回避)
各作 先頭+(無ければ)2-3巻ISBNを照会。 backup+changelog・可逆。
"""
import sys,re,json,time,shutil,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def lnm(t): return t.split('}')[-1]
def ndc(isbn):
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'1','query':f'isbn="{isbn}"'})
    for at in range(3):
        try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'M/0.1'}),timeout=20).read(); break
        except Exception:
            if at<2: time.sleep(1.5); continue
            return None
    try: root=ET.fromstring(b)
    except: return None
    subs=[]
    for rd in root.iter():
        if lnm(rd.tag)!='recordData': continue
        kids=list(rd); it=list(rd.iter()) if kids else (list(ET.fromstring(rd.text).iter()) if rd.text and '<' in rd.text else [])
        for el in it:
            if lnm(el.tag)=='subject' and (el.text or '').strip():
                subs.append(el.text.strip())
        break
    # NDC = 数字始まりのsubjectのみ(主題語は除く)
    ndcs=[s for s in subs if re.match(r'^\d',s)]
    if not ndcs: return None
    return ndcs

def main():
    # 現存の新作slug(rename後): created.jsonl + ndlverify-changelog の new_slug
    slugs=set()
    for l in open(ROOT/'data'/'seeds'/'torichigae-ndlverify-changelog.jsonl',encoding='utf-8'):
        slugs.add(json.loads(l)['new_slug'])
    slugs={s for s in slugs if (ROOT/'data'/'manga.v2'/f'{s}.yml').exists()}
    print(f'NDC判定 {len(slugs)} 新作',flush=True)
    bak=ROOT/'.cache'/f'ndc-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    manga=nonmanga=unknown=0; removed=[]
    for i,slug in enumerate(sorted(slugs),1):
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        isbns=[str(v.get('isbn13')) for e in d.get('editions',[]) for v in e.get('volumes',[]) if v.get('isbn13')]
        found=None; ismanga=False
        for ib in isbns[:3]:
            nd=ndc(ib); time.sleep(1.0)
            if nd:
                found=nd
                if any(x.startswith('726') for x in nd): ismanga=True; break
        if ismanga: manga+=1
        elif found is None: unknown+=1   # NDC取得不可=保持
        else:
            # NDC有るが726無し=非漫画 → 削除
            nonmanga+=1; removed.append((slug,d.get('title'),';'.join(found)))
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{slug}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.unlink()
        if i%30==0: print(f'  {i}/{len(slugs)} manga{manga} 非manga{nonmanga} 不明{unknown}',flush=True)
    with (ROOT/'data'/'seeds'/'torichigae-ndc-removed.tsv').open('w',encoding='utf-8') as f:
        f.write('slug\ttitle\tNDC\n')
        for s,t,n in removed: f.write(f'{s}\t{t}\t{n}\n')
    print(f'\nNDC判定完了: 漫画{manga} / 非漫画削除{nonmanga} / NDC不明=保持{unknown}')
    for s,t,n in removed[:20]: print(f'  削除 {s[:20]:20s}「{str(t)[:18]}」NDC={n[:20]}')

if __name__=='__main__': main()
