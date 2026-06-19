#!/usr/bin/env python3
"""アンソロ/作品集をシリーズ単位で統合(混ぜない)。各群: 巻を結合し series題に。 --apply。"""
import sys,os,time,shutil,json,re
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
# (canonical_slug, series_title, series_kana, [source_slugs])
GROUPS=[
 ('sasayananae','ささやななえ作品集','ササヤナナエサクヒンシュウ',['sasayananae','sasayananae-3186']),
 ('basara-3001','少年忍者バサラくん','ショウネンニンジャバサラクン',['basara-3001','basara-2592']),
 ('ribonmanga','りぼん新人まんが傑作集','リボンシンジンマンガケッサクシュウ',['ribonmanga','ribonmanga-5227']),
]
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def main():
    bak=ROOT/'.cache'/f'anth-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'; alias=yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    cl=(ROOT/'data'/'seeds'/'series-merge-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    for canon,title,kana,srcs in GROUPS:
        srcs=[s for s in srcs if (ROOT/'data'/'manga.v2'/f'{s}.yml').exists()]
        if len(srcs)<2: print('skip',canon,'(source不足)'); continue
        cd=yaml.safe_load((ROOT/'data'/'manga.v2'/f'{canon}.yml').read_text(encoding='utf-8'))
        # 全sourceの巻を収集(volume_label=元title)
        allv=[]
        for s in srcs:
            d=yaml.safe_load((ROOT/'data'/'manga.v2'/f'{s}.yml').read_text(encoding='utf-8'))
            story=str(d.get('title') or '')
            for e in d.get('editions',[]):
                for v in e.get('volumes',[]):
                    vv=dict(v); vv['volume_label']=story[:40]; vv['_date']=str(v.get('release_date') or '9999')
                    allv.append(vv)
        allv.sort(key=lambda v:(v['_date'],to13(v.get('isbn13'))))
        for i,v in enumerate(allv,1):
            v['number']=i; v.pop('_date',None)
        cd['title']=title; cd['title_kana']=kana; cd['title_romaji']=re.sub(r'[^a-z0-9 ]','',kana.lower())
        cd['editions']=[{'type':'standard','label':'通常版','publisher':cd.get('publisher'),'volumes':allv}]
        print(f'  {title}: {srcs} → {canon} {len(allv)}巻')
        if APPLY:
            y=yaml.dump(cd,allow_unicode=True,sort_keys=False,default_flow_style=False)
            for base in ('data/manga.v2','.preview-data/manga'):
                cf=ROOT/base/f'{canon}.yml'
                if cf.exists(): shutil.copy2(cf,bak/(base.replace('/','_')+'__'+canon+'.yml')); cf.write_text(y,encoding='utf-8')
                for s in srcs:
                    if s==canon: continue
                    f2=ROOT/base/f'{s}.yml'
                    if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+s+'.yml')); f2.unlink()
            for s in srcs:
                if s!=canon: alias[s]=canon
            cl.write(json.dumps({'canon':canon,'title':title,'merged':[s for s in srcs if s!=canon],'vols':len(allv),'at':st},ensure_ascii=False)+'\n')
    if APPLY:
        af.write_text(yaml.dump(alias,allow_unicode=True,sort_keys=True),encoding='utf-8'); print('適用 backup='+str(bak))
    else: print('\n(dry-run)')
    cl.close()
if __name__=='__main__': main()
