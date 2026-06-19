#!/usr/bin/env python3
"""
DUPLICATE手動群のcanonicalを私(AI)が裁定. cm104正式名＋メタ＋題名正しさでスコア→canonical決定。
credit和集合(堀井雄二型=トークン非重複の別人著者は保全)。 理由付きで出力。 --apply で統合(可逆)。
入力: data/seeds/dup-merge-manual.tsv  出力: dup-merge-judge.tsv + (apply時)alias/changelog
"""
import sys,io,csv,json,re,time,shutil,unicodedata
from pathlib import Path
from collections import Counter,defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
APPLY='--apply' in sys.argv
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def ncore(s):
    s=zen(str(s)); s=unicodedata.normalize('NFKC',s); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    return re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが)$')
def na(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s)); out=set()
    for p in re.split(r'[／/、,;・\s]+',s):
        p=re.sub(r'^\[[^\]]*\]','',p.strip()); p=ROLE.sub('',p).strip()
        if len(p)>=2: out.add(p.lower())
    return out
def toks(name):
    return set(t for t in re.split(r'[・\s]+',re.sub(r'[A-Za-z]','',str(name))) if len(t)>=2)
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    return yaml.load(fp.read_text(encoding='utf-8'),Loader=L) if fp.exists() else None
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def load_cm104():
    g=json.load(open(ROOT/'.cache'/'madb'/'metadata104.json',encoding='utf-8'))
    g=g.get('@graph',g) if isinstance(g,dict) else g
    idx=defaultdict(list)
    def cnm(r):
        v=r.get('ma:seriesName') or r.get('schema:name'); return v[0] if isinstance(v,list) else v
    for r in g:
        idx[ncore(cnm(r))].append((cnm(r),na(r.get('schema:creator'))))
    return idx

def main():
    print('cm104ロード...',flush=True); CM=load_cm104()
    groups=[]
    with open(ROOT/'data'/'seeds'/'dup-merge-manual.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        for x in r:
            if x: groups.append([s.strip() for s in x[0].split('|')])
    out=[]; merges=[]
    for gl in groups:
        mem=[(s,load(s)) for s in gl]; mem=[(s,d) for s,d in mem if d]
        if len(mem)<2: continue
        allauth=set()
        for _,d in mem:
            for a in (d.get('authors') or [])+(d.get('original_authors') or []): allauth|=na(a.get('name') if isinstance(a,dict) else a)
        # cm104 authoritative seriesName(著者一致)
        cm_names=[]
        for _,d in mem:
            for nm,au in CM.get(ncore(d.get('title')),[]):
                if allauth & au: cm_names.append(ncore(nm))
        cm_set=set(cm_names)
        # スコアリング
        best=None; bestsc=-99; reason=''
        for s,d in mem:
            sc=0; rs=[]
            tc=ncore(d.get('title'))
            if tc in cm_set: sc+=10; rs.append('cm104題一致')
            if d.get('wikidata_qid'): sc+=3; rs.append('qid有')
            ne=len(d.get('editions') or []); sc+=ne; rs.append(f'版{ne}')
            sc+=min(len(str(d.get('title'))),24)*0.1
            if re.search(r'-\d{4}(-\d+)?$',s): sc-=2; rs.append('年suffix')
            if sc>bestsc: bestsc=sc; best=(s,d); reason=','.join(rs)
        can,cd=best; drops=[s for s,_ in mem if s!=can]
        conf='HIGH' if (ncore(cd.get('title')) in cm_set) else ('MED' if cd.get('wikidata_qid') else 'LOW')
        # 保全すべき別人著者(canonicalに無くトークン非重複)
        can_tok=set();
        for a in (cd.get('authors') or [])+(cd.get('original_authors') or []): can_tok|=toks(a.get('name') if isinstance(a,dict) else a)
        preserve=[]
        for s,d in mem:
            if s==can: continue
            for a in (d.get('authors') or [])+(d.get('original_authors') or []):
                nm=a.get('name') if isinstance(a,dict) else a
                if toks(nm) and not (toks(nm)&can_tok):
                    preserve.append(a if isinstance(a,dict) else {'name':nm}); can_tok|=toks(nm)
        out.append([can,cd.get('title'),'|'.join(drops),conf,reason,';'.join(p['name'] for p in preserve)])
        merges.append((can,cd,drops,preserve,[m[1] for m in mem]))
    # 出力
    with (ROOT/'data'/'seeds'/'dup-merge-judge.tsv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['canonical','title','drops','confidence','reason','preserve_authors'])
        for r in out: w.writerow(r)
    print('判定:',dict(Counter(r[3] for r in out)),f'/ 計{len(out)}群')
    print('-- 裁定サンプル --')
    for r in out[:20]:
        pres=(' +保全:'+r[5]) if r[5] else ''
        print(f'  [{r[3]}] {r[0]}「{r[1][:16]}」← {r[2][:40]} ({r[4]}){pres}')
    if not APPLY:
        print('\n(dry-run。 --apply で統合)'); return
    # 適用
    alias={}; clog=[]; bak=ROOT/'.cache'/f'dup-judge-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    for can,cd,drops,preserve,allmem in merges:
        # union: 欠落scalar補填 + 欠edition追加 + preserve著者
        for d in allmem:
            for fld in ('wikidata_qid','synopsis','anilist_id','score','popularity','catch','demographic'):
                if not cd.get(fld) and d.get(fld): cd[fld]=d[fld]
            have=set(e.get('type') for e in (cd.get('editions') or []))
            for e in (d.get('editions') or []):
                if e.get('type') not in have: cd.setdefault('editions',[]).append(e); have.add(e.get('type'))
        if preserve:
            oa=cd.get('original_authors') or []; oa+= [p for p in preserve]; cd['original_authors']=oa
        out_y=yaml.dump(cd,allow_unicode=True,sort_keys=False,default_flow_style=False)
        for base in ('data/manga.v2','.preview-data/manga'):
            p=ROOT/base/f'{can}.yml'
            if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+can+'.yml')); p.write_text(out_y,encoding='utf-8')
        # canonicalがpreview未存在なら追加
        pv=ROOT/'.preview-data'/'manga'/f'{can}.yml'
        if not pv.exists(): pv.write_text(out_y,encoding='utf-8')
        for s in drops:
            alias[s]=can; clog.append({'dropped':s,'canonical':can})
            for base in ('data/manga.v2','.preview-data/manga'):
                p=ROOT/base/f'{s}.yml'
                if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+s+'.yml')); p.unlink()
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'
    cur=yaml.safe_load(af.read_text(encoding='utf-8')) if af.exists() else {}; cur=cur or {}; cur.update(alias)
    af.write_text(yaml.dump(cur,allow_unicode=True,sort_keys=True),encoding='utf-8')
    with (ROOT/'data'/'seeds'/'dup-merge-changelog.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'\n適用: {len(merges)}群 / drop {len(alias)} / backup {bak.name}',flush=True)

if __name__=='__main__': main()
