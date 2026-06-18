#!/usr/bin/env python3
"""
DUPLICATE一括統合(慎重). t3-consensus の DUPLICATE(同一ISBN・同著者)からslug群を作り、
★安全な「base＋数字/年サフィックス」型のみ自動統合。意味語サフィックスは手動送り。
canonical=base、メタ和集合(qid保持者から著者/qid/synopsis、欠落scalar補填、欠edition追加)、他drop+alias。可逆。
使い方: python _dup_merge_batch.py [--apply]
出力: data/seeds/dup-merge-alias.yml 追記 / dup-merge-changelog.jsonl / dup-merge-manual.tsv(手動送り)
"""
import sys,io,json,re,time,shutil
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
APPLY='--apply' in sys.argv
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
SAFE_SUF=re.compile(r'^[a-z]*\d{4}(-\d+)?$|^\d+$')   # 年/名+年/数字 のみ=機械生成サフィックス

class UF:
    def __init__(s): s.p={}
    def f(s,x):
        s.p.setdefault(x,x)
        while s.p[x]!=x: s.p[x]=s.p[s.p[x]]; x=s.p[x]
        return x
    def u(s,a,b): s.p[s.f(a)]=s.f(b)

def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    if not fp.exists(): return None
    try: return yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
    except: return None

def main():
    # DUPLICATE pairs
    uf=UF(); members=set()
    with open(ROOT/'data'/'seeds'/'t3-consensus.tsv',encoding='utf-8-sig') as f:
        r=__import__('csv').reader(f,delimiter='\t'); next(r)
        for x in r:
            if len(x)<11 or x[10]!='DUPLICATE': continue
            w,o=x[6],x[4]
            if not w or not o or o=='(所有者不明)': continue
            uf.u(w,o); members.add(w); members.add(o)
    groups=defaultdict(set)
    for m in members: groups[uf.f(m)].add(m)
    groups=[g for g in groups.values() if len(g)>=2]
    print(f'DUPLICATE群: {len(groups)}',flush=True)

    safe=[]; manual=[]
    for g in groups:
        gl=sorted(g)
        base=None
        for b in gl:
            others=[o for o in gl if o!=b]
            if others and all(o.startswith(b+'-') and SAFE_SUF.match(o[len(b)+1:]) for o in others):
                base=b; break
        if base: safe.append((base,[o for o in gl if o!=base]))
        else: manual.append(gl)
    print(f'安全自動(base+数字/年): {len(safe)}群 / 手動送り(意味語等): {len(manual)}群',flush=True)

    # 手動送り出力
    with (ROOT/'data'/'seeds'/'dup-merge-manual.tsv').open('w',encoding='utf-8-sig',newline='') as f:
        w=__import__('csv').writer(f,delimiter='\t'); w.writerow(['group_slugs'])
        for gl in manual: w.writerow([' | '.join(gl)])

    alias={}; clog=[]; applied=0
    bak=ROOT/'.cache'/f'dup-batch-bak-{time.strftime("%Y%m%d-%H%M%S")}'
    samples=[]
    for can,drops in safe:
        cd=load(can)
        if cd is None: continue
        ds=[(s,load(s)) for s in drops]; ds=[(s,d) for s,d in ds if d]
        # sanity: 同一ISBN共有 & 同著者(簡易)
        def isbns(d): return set(to13(v.get('isbn13')) for e in (d.get('editions') or []) for v in (e.get('volumes') or []) if to13(v.get('isbn13')))
        ci=isbns(cd)
        if not any(ci & isbns(d) for _,d in ds):
            manual.append([can]+drops); continue   # ISBN共有が確認できない→手動
        # union: qid保持dupから著者/qid/synopsis
        qid_src=None
        if not cd.get('wikidata_qid'):
            for _,d in ds:
                if d.get('wikidata_qid'): qid_src=d; break
        if qid_src:
            cd['wikidata_qid']=qid_src.get('wikidata_qid')
            if qid_src.get('authors'): cd['authors']=qid_src['authors']
            if qid_src.get('original_authors'): cd['original_authors']=qid_src['original_authors']
        for fld in ('synopsis','anilist_id','score','popularity','catch','demographic'):
            if not cd.get(fld):
                for _,d in ds:
                    if d.get(fld): cd[fld]=d[fld]; break
        have=set(e.get('type') for e in (cd.get('editions') or []))
        for _,d in ds:
            for e in (d.get('editions') or []):
                if e.get('type') not in have: cd.setdefault('editions',[]).append(e); have.add(e.get('type'))
        if len(samples)<12: samples.append((can,drops,[e.get('type') for e in cd.get('editions',[])]))
        if APPLY:
            bak.mkdir(parents=True,exist_ok=True)
            out=yaml.dump(cd,allow_unicode=True,sort_keys=False,default_flow_style=False)
            for base in ('data/manga.v2','.preview-data/manga'):
                p=ROOT/base/f'{can}.yml'
                if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+can+'.yml')); p.write_text(out,encoding='utf-8')
            for s in drops:
                alias[s]=can; clog.append({'dropped':s,'canonical':can})
                for base in ('data/manga.v2','.preview-data/manga'):
                    p=ROOT/base/f'{s}.yml'
                    if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+s+'.yml')); p.unlink()
            applied+=1
    if APPLY and alias:
        af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'
        cur=yaml.safe_load(af.read_text(encoding='utf-8')) if af.exists() else {}; cur=cur or {}; cur.update(alias)
        af.write_text(yaml.dump(cur,allow_unicode=True,sort_keys=True),encoding='utf-8')
        with (ROOT/'data'/'seeds'/'dup-merge-changelog.jsonl').open('a',encoding='utf-8') as f:
            st=time.strftime('%Y-%m-%dT%H:%M:%S')
            for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'\n{"適用" if APPLY else "DRY"}: 統合{applied if APPLY else len(safe)}群 / drop計{sum(len(d) for _,d in safe)} / 手動{len(manual)}群',flush=True)
    print('-- 安全統合サンプル(canonical ← drops) --')
    for can,drops,eds in samples: print(f'  {can} ← {drops}  editions={eds}')

if __name__=='__main__': main()
