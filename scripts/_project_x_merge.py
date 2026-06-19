#!/usr/bin/env python3
"""
プロジェクトX挑戦者たち 18作(宙出版コミック版・各話別作画) → 1シリーズに統合。
各巻=エピソード(発売日順にnumber)、volume_label=エピソード題、artists=[作画者]、原作=NHK制作班。
18個別作はalias+削除。 dry-run/--apply。
"""
import sys,glob,os,re,time,shutil,json
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def artist(au):
    # '笠原倫 作画・脚本' → '笠原倫'
    out=[]
    for a in au:
        nm=a.get('name') if isinstance(a,dict) else a
        nm=re.sub(r'\s*(作画・脚本|作画監修|作画|脚本|原作|with.*)$','',str(nm)).strip()
        if nm and nm not in out: out.append(nm)
    return out

def main():
    CANON='project-x-chousensha-tachi'
    fs=sorted(glob.glob(str(ROOT/'data'/'manga.v2'/'purojiekuto*.yml')))
    vols=[]; srcs=[]
    for fp in fs:
        d=yaml.safe_load(open(fp,encoding='utf-8'))
        slug=d.get('slug') or Path(fp).stem; srcs.append(slug)
        ep=str(d.get('title') or '')
        for e in d.get('editions',[]):
            for v in e.get('volumes',[]):
                ib=to13(v.get('isbn13'))
                vols.append({'isbn':ib,'date':str(v.get('release_date') or ''),'cover':v.get('cover_url'),
                             'ep':ep,'artists':artist(d.get('authors',[]))})
    vols.sort(key=lambda v:(v['date'] or '9999',v['isbn']))
    nv=[]
    for i,v in enumerate(vols,1):
        vv={'number':i,'isbn13':v['isbn'] or None,'volume_label':v['ep'][:40]}
        if v['cover']: vv['cover_url']=v['cover']
        if v['date']: vv['release_date']=v['date']
        if v['artists']: vv['artists']=v['artists']
        nv.append(vv)
    years=[int(v['date'][:4]) for v in vols if v['date'][:4].isdigit()]
    work={'slug':CANON,'title':'プロジェクトX挑戦者たち','title_kana':'プロジェクトエックスチョウセンシャタチ',
          'title_romaji':'project x chousensha tachi','year_started':min(years) if years else 2002,
          'year_ended':max(years) if years else 2005,
          'authors':[{'name':'NHKプロジェクトX制作班','role':'writer'}],'original_authors':[],'credits':[],
          'publisher':'(unknown)','publishers':[],'demographic':'seinen',
          'genres':['drama','historical'],'genres_provisional':True,'synopsis':'',
          'status':'completed','magazine':None,
          'editions':[{'type':'standard','label':'宙出版コミック版','publisher':'(unknown)','volumes':nv}],
          'note_origin':'プロジェクトX挑戦者たち=宙出版コミック版18話を1シリーズ統合(各話別作画・原作NHK)'}
    print(f'プロジェクトX: {len(srcs)}個別作 → 1シリーズ {len(nv)}巻(エピソード)')
    for vv in nv[:6]: print('  vol'+str(vv['number'])+' '+str(vv.get('isbn13'))+' '+str(vv.get('release_date'))+' 作画'+str(vv.get('artists'))+' 「'+vv['volume_label'][:18]+'」')
    print('  ...')
    if not APPLY:
        print('\n(dry-run。 --applyで統合)'); return
    bak=ROOT/'.cache'/f'projx-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    y=yaml.dump(work,allow_unicode=True,sort_keys=False,default_flow_style=False)
    for base in ('data/manga.v2','.preview-data/manga'):
        (ROOT/base/f'{CANON}.yml').write_text(y,encoding='utf-8')
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'; alias=yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    for slug in srcs:
        alias[slug]=CANON
        for base in ('data/manga.v2','.preview-data/manga'):
            f2=ROOT/base/f'{slug}.yml'
            if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+slug+'.yml')); f2.unlink()
    af.write_text(yaml.dump(alias,allow_unicode=True,sort_keys=True),encoding='utf-8')
    with (ROOT/'data'/'seeds'/'series-merge-changelog.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'canon':CANON,'merged':srcs,'vols':len(nv),'at':time.strftime('%Y-%m-%dT%H:%M:%S')},ensure_ascii=False)+'\n')
    print(f'\n統合適用: {len(srcs)}→1({CANON}) {len(nv)}巻 backup={bak}')

if __name__=='__main__': main()
