#!/usr/bin/env python3
"""
DUPLICATE統合(慎重・可逆): canonicalへメタ和集合→冗長slugをdrop+alias記録。 manga.v2+preview。
backupを取り、dup-merge-alias.yml と merge-changelog.jsonl に記録(復元可)。
※ここでは指定2件のみ(Dragon Quest / エスパー魔美)。
"""
import io,json,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L

MERGES=[
 {'canonical':'esper-mami','drop':['esper-mami-1996','esper-mami-1996-2'],
  'set':{'authors':[{'name':'藤子・F・不二雄','role':'writer_artist','kana':'フジコフジオF','romaji':'fujikofujio'}],
         'wikidata_qid':'Q17572'},
  'add_edition_from':('esper-mami-1996','bunkobon'),
  'fill_synopsis_from':'esper-mami-1996'},
 {'canonical':'dragon-quest-dai-no-daibouken','drop':['dragon-quest'],
  'append_original_author':{'name':'堀井雄二','role':'supervisor','kana':'ホリイユウジ','romaji':'horiiyuuji'}},
]

def main():
    bak=ROOT/'.cache'/f'dup-merge-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    alias={}; clog=[]
    for m in MERGES:
        can=m['canonical']
        # canonical 編集(manga.v2 で内容決定→両環境へ)
        cfp=ROOT/'data'/'manga.v2'/f'{can}.yml'
        d=yaml.load(cfp.read_text(encoding='utf-8'),Loader=L)
        for k,v in (m.get('set') or {}).items(): d[k]=v
        if m.get('append_original_author'):
            oa=d.get('original_authors') or []
            if not any(a.get('name')==m['append_original_author']['name'] for a in oa):
                oa.append(m['append_original_author']); d['original_authors']=oa
        if m.get('add_edition_from'):
            src_slug,etype=m['add_edition_from']
            sd=yaml.load((ROOT/'data'/'manga.v2'/f'{src_slug}.yml').read_text(encoding='utf-8'),Loader=L)
            srced=[e for e in (sd.get('editions') or []) if e.get('type')==etype]
            have=set(e.get('type') for e in (d.get('editions') or []))
            if srced and etype not in have: d.setdefault('editions',[]).append(srced[0])
        if m.get('fill_synopsis_from') and not d.get('synopsis'):
            sd=yaml.load((ROOT/'data'/'manga.v2'/f'{m["fill_synopsis_from"]}.yml').read_text(encoding='utf-8'),Loader=L)
            if sd.get('synopsis'): d['synopsis']=sd['synopsis']
        out=yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False)
        for base in ('data/manga.v2','.preview-data/manga'):
            p=ROOT/base/f'{can}.yml'
            if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+can+'.yml')); p.write_text(out,encoding='utf-8')
        # drop
        for ds in m['drop']:
            alias[ds]=can
            clog.append({'dropped':ds,'canonical':can})
            for base in ('data/manga.v2','.preview-data/manga'):
                p=ROOT/base/f'{ds}.yml'
                if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+ds+'.yml')); p.unlink()
        print(f'統合: {can} ← {m["drop"]}',flush=True)
    # alias 追記
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'
    cur=yaml.safe_load(af.read_text(encoding='utf-8')) if af.exists() else {}
    cur=cur or {}; cur.update(alias)
    af.write_text(yaml.dump(cur,allow_unicode=True,sort_keys=True),encoding='utf-8')
    with (ROOT/'data'/'seeds'/'dup-merge-changelog.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'alias {len(alias)}件 → dup-merge-alias.yml / backup {bak.name}',flush=True)

if __name__=='__main__': main()
