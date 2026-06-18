#!/usr/bin/env python3
"""
T3誤付与の3点合議(本番不変・台帳のみ)。
ある共有ISBNについて:
 - 楽天題(t3-ownership で算出済の owner) ＋ NDL著者 ＋ DB各作の著者 を突合。
 - 「誤付与作の著者 ≠ NDL著者」かつ「楽天題でも別作」=2ソース一致で高信頼の誤付与。
 - 正所有者 = 共有作のうち著者がNDL著者と一致する作。
出力: data/seeds/t3-consensus.tsv + 集計。
"""
import sys,json,csv,re,unicodedata
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
ROLE=re.compile(r'(著|作画|作|画|原作|漫画|編|原案|脚本|構成|協力|監修|訳|まんが|ストーリー|story|art)$')
def na(s):
    if not s: return set()
    s=unicodedata.normalize('NFKC',str(s))
    parts=re.split(r'[／/、,;・\s]+',s)
    out=set()
    for p in parts:
        p=p.strip()
        p=re.sub(r'^\[[^\]]*\]','',p)   # [原作]等
        p=ROLE.sub('',p).strip()
        p=re.sub(r'[（(].*?[）)]','',p)
        if len(p)>=2: out.add(p.lower())   # 大小無視(Clamp==CLAMP)
    return out
def amatch(a,b):
    if not a or not b: return None
    return len(a & b)>0

def main():
    # NDL isbn -> author/title
    ndl={}
    for l in (ROOT/'.cache'/'ndl-isbn.jsonl').open(encoding='utf-8'):
        try: r=json.loads(l)
        except: continue
        ndl[to13(r.get('isbn'))]={'a':na(r.get('author')),'t':r.get('title') or ''}
    # t3-ownership rows
    rows=[]
    with open(ROOT/'data'/'seeds'/'t3-ownership.tsv',encoding='utf-8-sig') as f:
        rd=csv.reader(f,delimiter='\t'); next(rd)
        for x in rd:
            if len(x)>=8: rows.append(x)  # shared_isbn,rk_title,n_owners,owner_slug,wrong_slug,wrong_vol,proposed,how
    slugs=set()
    for x in rows: slugs.add(x[3]); slugs.add(x[4])
    # slug -> authors(set)
    auth={}
    for s in slugs:
        fp=ROOT/'data'/'manga.v2'/f'{s}.yml'
        if not fp.exists(): continue
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        aset=set()
        for k in ('authors','original_authors'):
            for a in (d.get(k) or []):
                if isinstance(a,dict): aset|=na(a.get('name'))
                elif isinstance(a,str): aset|=na(a)
        auth[s]=aset
    out=[]; hi=0; lo=0
    for x in rows:
        ib=to13(x[0]); owner=x[3]; wrong=x[4]
        n=ndl.get(ib,{}); ndl_a=n.get('a',set()); ndl_t=n.get('t','')
        wrong_a=auth.get(wrong,set()); owner_a=auth.get(owner,set())
        wrong_vs_ndl = amatch(wrong_a,ndl_a)      # 誤付与作の著者がNDL著者と一致?
        owner_vs_ndl = amatch(owner_a,ndl_a)
        # 高信頼の誤付与 = NDL著者があり、誤付与作と不一致(=楽天題別作 と NDL著者不一致 の2ソース合致)
        conf='LOW'
        if not ib.startswith('9784'):
            conf='FOREIGN'   # 978-3等=外国版ISBN→別問題(drop候補)
        elif ndl_a:
            if wrong_vs_ndl is False and (owner_vs_ndl is True or owner=='(所有者不明)'):
                conf='HIGH'; hi+=1
            elif wrong_vs_ndl is True:
                conf='CONFLICT'   # NDL著者が誤付与作と一致=楽天と食い違い→人手
            else: lo+=1
        else: lo+=1
        out.append([ib,x[1][:24],ndl_t[:24],';'.join(sorted(ndl_a)),owner,';'.join(sorted(owner_a))[:20],
                    wrong,';'.join(sorted(wrong_a))[:20],x[5],x[6],conf])
    out.sort(key=lambda z:(z[10]!='HIGH',z[0]))
    p=ROOT/'data'/'seeds'/'t3-consensus.tsv'
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['shared_isbn','rk_title','ndl_title','ndl_author','owner_slug','owner_author','wrong_slug','wrong_author','wrong_vol','proposed_isbn','confidence'])
        for r in out: w.writerow(r)
    from collections import Counter
    c=Counter(r[10] for r in out)
    print('=== T3 3点合議 ===')
    print(f'誤付与行 {len(out):,}: {dict(c)}')
    print('  HIGH(楽天題別作 ＋ NDL著者不一致 の2ソース一致=高信頼の誤付与):', c.get("HIGH",0))
    print('  CONFLICT(NDL著者が誤付与作と一致=楽天と食違い→人手):', c.get("CONFLICT",0))
    print('  LOW(NDL著者欠落/判定不可):', c.get("LOW",0))
    print('-- HIGH サンプル --')
    for r in out[:12]:
        if r[10]=='HIGH': print(f'  {r[0]} NDL「{r[2]}」著={r[3]} | 正所有={r[4]}({r[5]}) 誤={r[6]}({r[7]})')
    print(f'→ {p}')

if __name__=='__main__': main()
