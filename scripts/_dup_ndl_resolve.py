#!/usr/bin/env python3
"""
DUPLICATE手動群をNDL実題で仕分け(慎重・可逆)。
各群: 共有ISBNのNDL実題を取得 → canonical=実題一致slug。
 - 他slugで実題に近い(題揺れ) = 真dup → drop+alias(canonicalへメタ和集合)。
 - 他slugで実題と別 = 別作が同ISBNを誤共有 → そのslugから共有ISBNを剥がす(→空化はre-ISBN台帳へ)。 dropしない。
 - NDL実題が取れない/どのslugとも合わない = uncertain(触らない)。
使い方: python _dup_ndl_resolve.py [--apply]
"""
import sys,io,csv,json,re,time,shutil,unicodedata,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
APPLY='--apply' in sys.argv
def lnm(t): return t.split('}')[-1]
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def ncore(s):
    s=zen(str(s)); s=unicodedata.normalize('NFKC',s); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'[．.]\s*\d+\s*$','',s)  # 末尾 .N(巻)除去
    low=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
    return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),low)
def lcs(a,b):
    if not a or not b: return 0
    pr=[0]*(len(b)+1); best=0
    for i in range(1,len(a)+1):
        cu=[0]*(len(b)+1)
        for j in range(1,len(b)+1):
            if a[i-1]==b[j-1]: cu[j]=pr[j-1]+1; best=max(best,cu[j])
        pr=cu
    return best
def similar(a,b):
    if not a or not b: return False
    if a in b or b in a: return True
    return lcs(a,b)>=4 and lcs(a,b)>=0.5*min(len(a),len(b))
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    return yaml.load(fp.read_text(encoding='utf-8'),Loader=L) if fp.exists() else None
def isbns(d): return [to13(v.get('isbn13')) for e in (d.get('editions') or []) for v in (e.get('volumes') or []) if to13(v.get('isbn13'))]

# NDL cache
NCACHE={}
cf=ROOT/'.cache'/'ndl-isbn.jsonl'
if cf.exists():
    for l in cf.open(encoding='utf-8'):
        try: r=json.loads(l); NCACHE[to13(r.get('isbn'))]=r.get('title') or ''
        except: pass
def ndl_title(isbn):
    if isbn in NCACHE: return NCACHE[isbn]
    u='https://ndlsearch.ndl.go.jp/api/sru?'+urllib.parse.urlencode({'operation':'searchRetrieve','recordSchema':'dcndl','recordPacking':'xml','maximumRecords':'1','query':f'isbn="{isbn}"'})
    try: b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'MANGAL/0.1'}),timeout=20).read()
    except Exception: NCACHE[isbn]=''; return ''
    t=''
    try:
        for rd in ET.fromstring(b).iter():
            if lnm(rd.tag)!='recordData': continue
            it=list(rd) and rd.iter() or (ET.fromstring(rd.text).iter() if rd.text and '<' in rd.text else [])
            for el in it:
                if lnm(el.tag)=='title' and (el.text or '').strip(): t=el.text.strip(); break
            break
    except Exception: pass
    NCACHE[isbn]=t; time.sleep(1.0); return t

def main():
    groups=[]
    with open(ROOT/'data'/'seeds'/'dup-merge-manual.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            if x: groups.append([s.strip() for s in x[0].split('|')])
    rows=[]; merges=[]; strips=[]; t0=time.time()
    for gi,gl in enumerate(groups,1):
        mem=[(s,load(s)) for s in gl]; mem=[(s,d) for s,d in mem if d]
        if len(mem)<2: continue
        # 共有ISBN
        sets=[set(isbns(d)) for _,d in mem]
        shared=set.intersection(*sets) if sets else set()
        probe=sorted(shared)[0] if shared else (isbns(mem[0][1])[0] if isbns(mem[0][1]) else None)
        rt=ndl_title(probe) if probe else ''
        rc=ncore(rt)
        if not rc:
            rows.append(['UNCERTAIN','|'.join(s for s,_ in mem),'(NDL実題なし)','']); continue
        if len(mem)>=4:
            rows.append(['DEFER-SERIESFRAG','|'.join(s for s,_ in mem),f'NDL「{rt[:22]}」(≥4作=シリーズ断片の疑い)','']); continue
        # canonical=実題に最も近い(同点は完全一致優先→短いslug)
        def key(sd):
            c=ncore(sd[1].get('title')); return (lcs(c,rc), 1 if c==rc else 0, -len(sd[0]))
        scored=sorted(mem,key=key,reverse=True)
        can,cd=scored[0]; can_c=ncore(cd.get('title'))
        # 非canonical: 全員が「実題と明確に別(続編/表記揺れでない)」の時だけ strip。 1人でも類似(dup/続編疑い)→群ごと保留
        nonc=[(s,d) for s,d in mem if s!=can]
        if any(similar(ncore(d.get('title')),rc) or similar(ncore(d.get('title')),can_c) for s,d in nonc):
            rows.append(['DEFER-SIMILAR',f'{can}','|'.join(s for s,_ in mem)+f' NDL「{rt[:18]}」(類似=続編/dup疑い)','']); continue
        rows.append(['STRIP',can,f'NDL「{rt[:22]}」 別作ISBN剥がし={[s for s,_ in nonc]}',''])
        for s,d in nonc: strips.append((s,d,shared))
        if gi%15==0: print(f'  {gi}/{len(groups)} [{time.time()-t0:.0f}s]',flush=True)
    print('\n=== NDL仕分け ===')
    from collections import Counter
    print('群:',Counter(r[0] for r in rows))
    print('真dup統合(canonical←dup):',sum(len(m[2]) for m in merges),'件 / 別作ISBN剥がし:',len(strips),'件')
    for r in rows[:24]:
        if r[0]=='RESOLVE': print(f'  {r[1]} : {r[2]}')
    print('-- UNCERTAIN --',[r[1] for r in rows if r[0]=='UNCERTAIN'][:10])
    if not APPLY:
        print('\n(dry-run)'); return
    # 適用
    bak=ROOT/'.cache'/f'dup-ndl-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    alias={}; clog=[]; striplog=[]
    def writeboth(slug,d):
        out=yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False)
        for base in ('data/manga.v2','.preview-data/manga'):
            p=ROOT/base/f'{slug}.yml'
            if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+slug+'.yml')); p.write_text(out,encoding='utf-8')
        pv=ROOT/'.preview-data'/'manga'/f'{slug}.yml'
        if not pv.exists(): pv.write_text(out,encoding='utf-8')
    for can,cd,dups in merges:
        for s,d in dups:
            for fld in ('wikidata_qid','synopsis','anilist_id','score','popularity','catch','demographic'):
                if not cd.get(fld) and d.get(fld): cd[fld]=d[fld]
            have=set(e.get('type') for e in (cd.get('editions') or []))
            for e in (d.get('editions') or []):
                if e.get('type') not in have: cd.setdefault('editions',[]).append(e); have.add(e.get('type'))
        writeboth(can,cd)
        for s,d in dups:
            alias[s]=can; clog.append({'dropped':s,'canonical':can})
            for base in ('data/manga.v2','.preview-data/manga'):
                p=ROOT/base/f'{s}.yml'
                if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+s+'.yml')); p.unlink()
    for s,d,shared in strips:
        ch=False
        for e in (d.get('editions') or []):
            keep=[v for v in (e.get('volumes') or []) if to13(v.get('isbn13')) not in shared]
            if len(keep)!=len(e.get('volumes') or []): e['volumes']=keep; ch=True
        d['editions']=[e for e in (d.get('editions') or []) if e.get('volumes')]
        if ch: writeboth(s,d); striplog.append({'slug':s,'stripped_isbns':sorted(shared)})
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'
    cur=yaml.safe_load(af.read_text(encoding='utf-8')) if af.exists() else {}; cur=cur or {}; cur.update(alias)
    af.write_text(yaml.dump(cur,allow_unicode=True,sort_keys=True),encoding='utf-8')
    with (ROOT/'data'/'seeds'/'dup-merge-changelog.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    with (ROOT/'data'/'seeds'/'dup-strip-changelog.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for r in striplog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    # NDLキャッシュ更新保存
    with cf.open('a',encoding='utf-8') as f:
        pass
    print(f'\n適用: 統合drop {len(alias)} / 別作ISBN剥がし {len(striplog)} / backup {bak.name}',flush=True)

if __name__=='__main__': main()
