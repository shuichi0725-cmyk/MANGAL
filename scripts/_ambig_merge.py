#!/usr/bin/env python3
"""
同名AMBIG(巻相補=分裂)9を慎重に統合。各群: 同一著者+巻番号disjoint+ISBN帯近似を確認し
canonical(vol1側/最多巻/きれいslug)へ他slugの巻をmerge→alias+削除。
dry-run/--apply。
"""
import sys,csv,re,time,shutil,json
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def info(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    if not fp.exists(): return None
    d=yaml.safe_load(fp.read_text(encoding='utf-8'))
    vols=set(); bands=set()
    for e in d.get('editions',[]):
        for v in e.get('volumes',[]):
            if v.get('number'): vols.add(int(v['number']))
            ib=to13(v.get('isbn13'))
            if ib: bands.add(ib[3:8])
    au=set(a.get('name') for a in (d.get('authors') or []))
    return {'d':d,'vols':vols,'bands':bands,'au':au,'title':d.get('title'),
            'n':sum(len(e.get('volumes',[])) for e in d.get('editions',[]))}

def main():
    ambig=[x[0] for x in csv.reader(open(ROOT/'data'/'seeds'/'samename-investigate.tsv',encoding='utf-8-sig'),delimiter='\t') if x[0]!='title' and x[1].startswith('AMBIG')]
    # samename-auditからslug取得
    title2slugs={}
    for x in csv.reader(open(ROOT/'data'/'seeds'/'samename-audit.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='title': continue
        title2slugs[x[0]]=[p.split('(')[0].strip() for p in x[2].split('|')]
    plans=[]
    for title in ambig:
        slugs=title2slugs.get(title,[])
        I={s:info(s) for s in slugs}; I={s:i for s,i in I.items() if i}
        if len(I)<2: continue
        sl=list(I)
        au_all=set.union(*[I[s]['au'] for s in sl]) if sl else set()
        au_shared=set.intersection(*[I[s]['au'] for s in sl]) if all(I[s]['au'] for s in sl) else set()
        # 巻overlap
        allvols=[I[s]['vols'] for s in sl]
        ov=0
        for i in range(len(sl)):
            for j in range(i+1,len(sl)):
                a,b=allvols[i],allvols[j]
                if a and b: ov=max(ov,len(a&b)/min(len(a),len(b)))
        # band近似
        ab=set.union(*[I[s]['bands'] for s in sl]) if sl else set()
        same_band=len(ab)<=2
        canon=sorted(sl,key=lambda s:(0 if (I[s]['vols'] and min(I[s]['vols'])==1) else 1,-I[s]['n']))[0]
        dups=[s for s in sl if s!=canon]
        confident = bool(au_shared) and ov<0.2
        plans.append((title,canon,dups,I,confident,au_shared,ov,same_band))
    print(f'AMBIG {len(plans)}件:')
    for title,canon,dups,I,conf,aus,ov,sb in plans:
        ranges={s:(min(I[s]['vols']) if I[s]['vols'] else '?',max(I[s]['vols']) if I[s]['vols'] else '?') for s in [canon]+dups}
        rs=' / '.join(f'{s}[v{ranges[s][0]}-{ranges[s][1]}]' for s in [canon]+dups)
        tag='OK' if conf else '要確認'; bd='同' if sb else '異'
        print('  ['+tag+']「'+title[:14]+'」keep='+canon+' 著共有'+str(bool(aus))+' 巻重複'+format(ov,'.0%')+' band'+bd)
        print(f'        {rs}')
    if not APPLY:
        print('\n(dry-run。 --applyで確証分mergeを実行)'); return
    bak=ROOT/'.cache'/f'ambig-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'; alias=yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    lf=(ROOT/'data'/'seeds'/'ambig-merge-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S'); n=0
    for title,canon,dups,I,conf,aus,ov,sb in plans:
        if not conf: continue
        cd=I[canon]['d']; cisb=set(to13(v.get('isbn13')) for e in cd.get('editions',[]) for v in e.get('volumes',[]) if v.get('isbn13'))
        cvol=I[canon]['vols']
        for dup in dups:
            added=[]
            for e in I[dup]['d'].get('editions',[]):
                for v in e.get('volumes',[]):
                    ib=to13(v.get('isbn13'))
                    if (ib and ib not in cisb) or (not ib and v.get('number') not in cvol):
                        tgt=next((x for x in cd.get('editions',[]) if x.get('type')=='standard'),cd['editions'][0])
                        tgt['volumes'].append(v)
                        if ib: cisb.add(ib)
                        if v.get('number'): cvol.add(v['number'])
                        added.append(ib or ('vol'+str(v.get('number'))))
            alias[dup]=canon
            lf.write(json.dumps({'dup':dup,'canon':canon,'merged':added,'at':st},ensure_ascii=False)+'\n')
        # sort canon volumes by number
        for e in cd.get('editions',[]):
            e['volumes']=sorted(e['volumes'],key=lambda v:(v.get('number') or 0))
        for base in ('data/manga.v2','.preview-data/manga'):
            cf=ROOT/base/f'{canon}.yml'
            if cf.exists(): shutil.copy2(cf,bak/(base.replace('/','_')+'__'+canon+'.yml')); cf.write_text(yaml.dump(cd,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
            for dup in dups:
                df=ROOT/base/f'{dup}.yml'
                if df.exists(): shutil.copy2(df,bak/(base.replace('/','_')+'__'+dup+'.yml')); df.unlink()
        n+=1
    af.write_text(yaml.dump(alias,allow_unicode=True,sort_keys=True),encoding='utf-8'); lf.close()
    print(f'\n統合適用: {n}群 / backup={bak}')

if __name__=='__main__': main()
