#!/usr/bin/env python3
"""
ISBN誤共有 un-merge ①②:
 ① series-dedup: ギリシア神話8→manga-girishia-shinwa / プリンセス → canonical残しalias+削除
 ② de-interleave: 共有ISBN集合を種1/楽天の真(題・著者)で各エントリに振り分け→各作を再構築(両方生存)
dry-run/--apply。 backup+changelog+alias。
"""
import sys,json,re,unicodedata,time,shutil,json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def first(v):
    if isinstance(v,list):
        for x in v:
            if isinstance(x,str): return x
            if isinstance(x,dict) and x.get('@value'): return x['@value']
    return v
def norm(s): return re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-0-9０-９]','',unicodedata.normalize('NFKC',str(s or ''))).lower()
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def naz(s): return hk(norm(s))

DEDUP=[('manga-girishia-shinwa',['aporon-no-kanashimi','eiyuu-herakuresu','higeki-no-ou-oidipusu','meikai-no-orufeusu','odeyusseusu-no-koukai','oryunposu-no-kamigami','toroi-no-mokuba']),
       ('idol-sousei-densetsu-princess',['princess'])]
DEINT=[['cue-2004','cue'],['shinpika-mizuki-shigeru-den','watashi-ha-gegege'],
       ['besuteia','ryuugetsushou'],['akai-hitsuji-no-kokuin','hakushaku-cain','kafuka','wasure-rareta-juliet']]

def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    return yaml.safe_load(fp.read_text(encoding='utf-8')) if fp.exists() else None

def main():
    print('種1+楽天ロード...',flush=True)
    TT={}; TA={}
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata101.json',encoding='utf-8'))['@graph']
    for r in g:
        ib=to13(first(r.get('schema:isbn')))
        if ib: TT[ib]=first(r.get('schema:name')) or ''; TA[ib]=naz(first(r.get('schema:creator')) or '')
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=J.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        it=o.get('item') or {}
        if ib and it and ib not in TT: TT[ib]=it.get('title',''); TA[ib]=naz(it.get('author',''))
    print('loaded',flush=True)

    plan_deint=[]  # (slug, new_editions, kept_count)
    for grp in DEINT:
        works={s:load(s) for s in grp}
        sig={s:(naz(works[s].get('title')), set(naz(a.get('name')) for a in (works[s].get('authors') or []))) for s in grp if works[s]}
        # master pool = 最多巻のwork
        master=max((s for s in grp if works[s]),key=lambda s:sum(len(e.get('volumes',[])) for e in works[s].get('editions',[])))
        assign={s:[] for s in grp}; unassigned=[]
        for e in works[master].get('editions',[]):
            for v in e.get('volumes',[]):
                ib=to13(v.get('isbn13'))
                tt=naz(TT.get(ib,'')); ta=TA.get(ib,'')
                best=None; bestsc=0
                for s in grp:
                    if s not in sig: continue
                    wt,wa=sig[s]; sc=0
                    if wt and (wt in tt or tt in wt): sc+=2
                    if ta and wa and (ta in wa or any(ta in x or x in ta for x in wa)): sc+=2
                    if sc>bestsc: bestsc=sc; best=s
                if best and bestsc>0: assign[best].append((e.get('type'),v,ib,TT.get(ib,'')))
                else: unassigned.append((ib,TT.get(ib,'')))
        print(f'\n■de-interleave {grp} (master={master})')
        for s in grp:
            print(f'   {s}: {len(assign[s])}巻 ← '+', '.join(sorted(set(x[3][:14] for x in assign[s]))[:4]))
        if unassigned: print(f'   ⚠未割当 {len(unassigned)}: {unassigned[:4]}')
        # 新edition構築(typeごとにまとめ・release_date順renumber)
        def numof(title,fallback):
            m=re.search(r'[（(]?\s*(\d{1,3})\s*[)）]?\s*$',re.sub(r'(巻|vol\.?|第)','',str(title)))
            return int(m.group(1)) if m else (fallback or 1)
        for s in grp:
            if s not in sig: continue
            byed={}
            for et,v,ib,tt in assign[s]:
                v['number']=numof(tt,v.get('number')); byed.setdefault(et,[]).append(v)
            neweds=[]
            for et,vs in byed.items():
                vs=sorted(vs,key=lambda v:(v.get('number') or 0))
                neweds.append({'type':et,'volumes':vs})
            plan_deint.append((s,neweds,len(assign[s]),works[s]))
    # ① dedup
    print('\n■series-dedup:')
    for canon,dups in DEDUP:
        print(f'   keep {canon} ← remove {dups}')

    if not APPLY:
        print('\n(dry-run。 --applyで適用)'); return
    bak=ROOT/'.cache'/f'unmerge-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'; alias=yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    lf=(ROOT/'data'/'seeds'/'unmerge-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    needs=[]
    # ② 各作のeditions差し替え
    for s,neweds,nv,orig in plan_deint:
        if nv==0:
            # 実在作だがこの束にISBN無し→removeしてneeds-content記録(空でbuild壊さない)
            needs.append(s)
            for base in ('data/manga.v2','.preview-data/manga'):
                fp=ROOT/base/f'{s}.yml'
                if fp.exists(): shutil.copy2(fp,bak/(base.replace('/','_')+'__'+s+'.yml')); fp.unlink()
            lf.write(J.dumps({'deint_empty_needs_content':s,'at':st},ensure_ascii=False)+'\n')
            print('  removed(empty→needs-content)',s); continue
        for base in ('data/manga.v2','.preview-data/manga'):
            fp=ROOT/base/f'{s}.yml'
            if not fp.exists(): continue
            d=yaml.safe_load(fp.read_text(encoding='utf-8'))
            shutil.copy2(fp,bak/(base.replace('/','_')+'__'+s+'.yml'))
            # neweds の volumes は master由来。slug自身のeditionにISBNで対応する巻を残す方式に統一
            d['editions']=[{k:v for k,v in ed.items()} for ed in neweds]
            fp.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False),encoding='utf-8')
        lf.write(J.dumps({'deint':s,'vols':nv,'at':st},ensure_ascii=False)+'\n')
    # ① dedup削除
    for canon,dups in DEDUP:
        for dup in dups:
            alias[dup]=canon
            for base in ('data/manga.v2','.preview-data/manga'):
                fp=ROOT/base/f'{dup}.yml'
                if fp.exists(): shutil.copy2(fp,bak/(base.replace('/','_')+'__'+dup+'.yml')); fp.unlink()
            lf.write(J.dumps({'dedup':dup,'canon':canon,'at':st},ensure_ascii=False)+'\n')
    af.write_text(yaml.dump(alias,allow_unicode=True,sort_keys=True),encoding='utf-8'); lf.close()
    if needs:
        p=ROOT/'data'/'seeds'/'unmerge-needs-content.tsv'
        with open(p,'a',encoding='utf-8') as f:
            for s in needs: f.write(s+'\t'+st+'\n')
        print('needs-content(別途ISBN探し):',needs)
    print(f'\n適用完了。 de-interleave {len([p for p in plan_deint if p[2]>0])}作 / 空→needs {len(needs)} / dedup {sum(len(d) for _,d in DEDUP)}削除。 backup={bak}')

if __name__=='__main__': main()
