#!/usr/bin/env python3
"""
釣りキチ三平: Wikipedia wikitext から KC全65 と プラチナ全47 の各巻ISBN+発売日を抽出し、
tsurikichi-sanpei の standard(KC65)を正ISBN化＋プラチナ47 editionを追加。 cover は別途楽天で。
--apply で適用(可逆backup)。
"""
import sys,re,io,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def isbn13(s):
    s=re.sub(r'[^0-9Xx]','',s)
    if len(s)==13: return s
    if len(s)==10:
        core='978'+s[:9]; t=0
        for i,c in enumerate(core): t+=int(c)*(1 if i%2==0 else 3)
        return core+str((10-t%10)%10)
    return ''
def parse_section(t,label):
    i=t.find(label)
    if i<0: return []
    chunk=t[i:]
    # 次の版ラベル(〉、全N巻) or 見出し(==) まで
    m=re.search(r'〉、全\d+巻|\n==[^=]',chunk[len(label):])
    if m: chunk=chunk[:len(label)+m.start()]
    vols=[]
    for line in chunk.splitlines():
        if not line.lstrip().startswith('*#'): continue
        mi=re.search(r'\{\{ISBN2?\|([0-9\-Xx]+)\}\}',line)
        md=re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日',line)
        ib=isbn13(mi.group(1)) if mi else None
        date=f'{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}' if md else None
        vols.append({'number':len(vols)+1,'isbn13':ib,'release_date':date,'cover_url':None})
    return vols

def main():
    t=(ROOT/'.cache'/'tsurikichi-wiki.txt').read_text(encoding='utf-8')
    kc=parse_section(t,'講談社コミックス〉、全65巻')
    pt=parse_section(t,'講談社プラチナコミックス〉、全47巻')
    kc_i=sum(1 for v in kc if v['isbn13']); pt_i=sum(1 for v in pt if v['isbn13'])
    print(f'KC: {len(kc)}巻 (ISBN有 {kc_i})')
    print(f'プラチナ: {len(pt)}巻 (ISBN有 {pt_i})')
    print('KC例:',[(v['number'],v['isbn13'],v['release_date']) for v in kc[:2]+kc[-1:]])
    print('プラチナ例:',[(v['number'],v['isbn13'],v['release_date']) for v in pt[:2]+pt[-1:]])
    if len(kc)!=65 or len(pt)!=47:
        print('!! 巻数が65/47でない→抽出見直し要。 適用中止');
        if APPLY: return
    if not APPLY:
        print('\n(dry-run)'); return
    for base in ('data/manga.v2','.preview-data/manga'):
        fp=ROOT/base/'tsurikichi-sanpei.yml'
        if not fp.exists(): continue
        d=yaml.safe_load(fp.read_text(encoding='utf-8'))
        shutil.copy2(fp,ROOT/'.cache'/(base.replace('/','_')+'__tsurikichi-sanpei.pre-build.yml'))
        # standard を KC65(ISBN付)で置換、プラチナ(renewal)追加。 label/imprint必須
        eds=[{'type':'standard','label':'通常版','publisher':'講談社','imprint':'講談社コミックス','volumes':kc},
             {'type':'renewal','label':'プラチナコミックス','publisher':'講談社','imprint':'講談社プラチナコミックス','volumes':pt}]
        d['editions']=eds
        fp.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
        print('適用',base)
    print('KC65(ISBN化)+プラチナ47 構築完了。 次=楽天で書影付与')

if __name__=='__main__': main()
