#!/usr/bin/env python3
"""
同名COPY(ISBN高一致=重複)のdedup(慎重)。overlap>=0.95 & 2-3エントリのクリーンな分のみ。
canonical=最多巻(tie→suffix無いslug)。 他エントリの欠巻をcanonicalにmerge→dup削除→alias。
複雑(こち亀89%/日本の歴史多数/魔法科71%/50%)は除外=手動。 dry-run/--apply。
"""
import sys,csv,re,time,shutil,json
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
EXCLUDE={'こちら葛飾区亀有公園前派出所','日本の歴史','魔法科高校の劣等生','NHKその時歴史が動いた','少年マガジン大全集復刻版'}
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    if not fp.exists(): return None
    d=yaml.safe_load(fp.read_text(encoding='utf-8'))
    isb=set()
    for e in d.get('editions',[]):
        for v in e.get('volumes',[]):
            ib=to13(v.get('isbn13'))
            if ib: isb.add(ib)
    return {'d':d,'isbns':isb,'n':sum(len(e.get('volumes',[])) for e in d.get('editions',[]))}
def clean_slug_rank(s):
    # suffix(年/数字)があるほど大きい=canonicalに選ばれにくい
    return (1 if re.search(r'-(19|20)\d\d(-\d+)?$',s) or re.search(r'-\d+$',s) else 0, len(s))

def main():
    plans=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'samename-audit.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='title' or x[0] in EXCLUDE: continue
        title=x[0]; slugs=[p.split('(')[0].strip() for p in x[2].split('|')]
        infos={s:load(s) for s in slugs}; infos={s:i for s,i in infos.items() if i}
        if len(infos)<2 or len(infos)>3: continue
        # 最大overlap
        sl=list(infos); mx=0
        for i in range(len(sl)):
            for j in range(i+1,len(sl)):
                a,b=infos[sl[i]]['isbns'],infos[sl[j]]['isbns']
                if a and b: mx=max(mx,len(a&b)/min(len(a),len(b)))
        if mx<0.95: continue
        # canonical=最多巻、tie→きれいなslug
        canon=sorted(sl,key=lambda s:(-infos[s]['n'],clean_slug_rank(s)))[0]
        dups=[s for s in sl if s!=canon]
        plans.append((title,canon,dups,infos,mx))
    print(f'クリーン100%重複(2-3entry): {len(plans)}件')
    for title,canon,dups,infos,mx in plans:
        cn=infos[canon]['n']; dl=[(d,infos[d]['n']) for d in dups]
        print(f'  「{title[:16]}」 keep={canon}({cn}) ← dup {dl} (一致{mx:.0%})')
    if not APPLY:
        print('\n(dry-run。 --applyで dedup実行)'); return
    bak=ROOT/'.cache'/f'samededup-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'
    alias=yaml.safe_load(af.read_text(encoding='utf-8')) if af.exists() else {}; alias=alias or {}
    lf=(ROOT/'data'/'seeds'/'samename-dedup-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    for title,canon,dups,infos,mx in plans:
        cd=infos[canon]['d']; cisb=infos[canon]['isbns']
        for dup in dups:
            # dupの欠巻(canonにないISBN)をcanonのstandardにmerge
            dd=infos[dup]['d']; added=[]
            for e in dd.get('editions',[]):
                for v in e.get('volumes',[]):
                    if to13(v.get('isbn13')) and to13(v.get('isbn13')) not in cisb:
                        tgt=next((x for x in cd.get('editions',[]) if x.get('type')=='standard'),cd['editions'][0])
                        tgt['volumes'].append(v); cisb.add(to13(v.get('isbn13'))); added.append(to13(v.get('isbn13')))
            alias[dup]=canon
            lf.write(json.dumps({'dup':dup,'canon':canon,'merged':added,'at':st},ensure_ascii=False)+'\n')
        # 書き出し: canon更新, dup削除(両base)
        for base in ('data/manga.v2','.preview-data/manga'):
            cf=ROOT/base/f'{canon}.yml'
            if cf.exists():
                shutil.copy2(cf,bak/(base.replace('/','_')+'__'+canon+'.yml'))
                cf.write_text(yaml.dump(cd,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            for dup in dups:
                df=ROOT/base/f'{dup}.yml'
                if df.exists(): shutil.copy2(df,bak/(base.replace('/','_')+'__'+dup+'.yml')); df.unlink()
    af.write_text(yaml.dump(alias,allow_unicode=True,sort_keys=True),encoding='utf-8')
    lf.close()
    print(f'\ndedup適用: {len(plans)}件 / backup={bak}')

if __name__=='__main__': main()
