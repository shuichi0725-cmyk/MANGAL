#!/usr/bin/env python3
"""
T3混入除去(慎重・可逆)。 t3-consensus.tsv の HIGH を確定根拠に、誤付与作から他作ISBNの巻を除去。
適用条件(安全側):
 - 対象作 = wrong_slug のうち「HIGH行を1つ以上持ち、DUPLICATE行を持たない」作のみ。
 - 除去ISBN = その作の HIGH ＋ LOW の shared_isbn(所有者確定の汚染作なので同列扱い)。CONFLICT/FOREIGN/DUPLICATEは除外。
 - 巻は **isbn13一致で除去**(巻番号では消さない=同名別版の事故防止)。空になったeditionは削除。
 - 全除去を changelog に記録(可逆)。 preview と manga.v2 の両方へ。
使い方: python _t3_apply.py [--dry-run]
"""
import sys,io,json,csv,time,shutil
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
DRY='--dry-run' in sys.argv
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    rows=[]
    with open(ROOT/'data'/'seeds'/'t3-consensus.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r); rows=[x for x in r]
    byw=defaultdict(list)
    for x in rows: byw[x[6]].append(x)   # wrong_slug
    plan={}   # slug -> {isbn:owner}
    for slug,xs in byw.items():
        conf=set(x[10] for x in xs)
        if 'HIGH' not in conf: continue          # HIGH無し=対象外
        if 'DUPLICATE' in conf: continue          # 重複混在=統合ゾーン→保留
        rem={}
        for x in xs:
            if x[10] in ('HIGH','LOW'):
                ib=to13(x[0])
                if ib: rem[ib]=x[4]   # owner
        if rem: plan[slug]=rem
    # ★全巻除去で空になる作はスキップ(=丸ごと別作の重複/誤帰属=drop/再ISBN案件で危険ゾーン→保留)
    deferred=[]
    safe={}
    for slug,rem in plan.items():
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        # ★ISBN無し巻も含めて全巻で数える(ワースト=小室の本物vol1-4はISBN無し→残すべき)
        total=0; removed=0
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                total+=1
                ib=to13(v.get('isbn13'))
                if ib and ib in rem: removed+=1
        if total>0 and removed<total: safe[slug]=rem   # 何か残る(ISBN無しの本物含む)=部分除去で安全
        else: deferred.append((slug,total))             # 全巻が除去対象=真の空化
    with (ROOT/'data'/'seeds'/'t3-deferred-emptied.tsv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['slug','all_vols_are_otherworks'])
        for s,n in deferred: w.writerow([s,n])
    plan=safe
    works=len(plan); total_isbn=sum(len(v) for v in plan.values())
    print(f'安全対象作(部分除去で残る): {works} / 除去ISBN(延べ): {total_isbn} / 保留(空化=別作丸ごと): {len(deferred)}',flush=True)
    if DRY:
        for s,r in list(plan.items())[:10]: print(f'  {s}: {len(r)}巻除去 (owner例 {list(r.values())[0]})')
        return
    bak=ROOT/'.cache'/f't3-fix-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    clog=[]; touched=0
    for base in (ROOT/'data'/'manga.v2', ROOT/'.preview-data'/'manga'):
        for slug,rem in plan.items():
            fp=base/f'{slug}.yml'
            if not fp.exists(): continue
            raw=fp.read_text(encoding='utf-8'); hdr=raw.split('\n',1)[0] if raw.startswith('#') else None
            d=yaml.load(raw,Loader=L)
            if not isinstance(d,dict): continue
            ch=False; neweds=[]
            for e in (d.get('editions') or []):
                keep=[]
                for v in (e.get('volumes') or []):
                    ib=to13(v.get('isbn13'))
                    if ib in rem:
                        ch=True
                        if base.name=='manga.v2':
                            clog.append({'slug':slug,'edition':e.get('type'),'number':v.get('number'),'removed_isbn':ib,'owner':rem[ib]})
                    else: keep.append(v)
                if keep:
                    e['volumes']=keep; neweds.append(e)
                # 空edition は捨てる(neweds に入れない)
                elif not keep and (e.get('volumes')):
                    ch=True
            if ch:
                touched+=1
                shutil.copy2(fp,bak/(base.name+'__'+fp.name))
                d['editions']=neweds
                buf=io.StringIO()
                if hdr: buf.write(hdr+'\n')
                yaml.dump(d,buf,allow_unicode=True,sort_keys=False,default_flow_style=False)
                fp.write_text(buf.getvalue(),encoding='utf-8')
    if clog:
        with (ROOT/'data'/'seeds'/'t3-fix-changelog.jsonl').open('a',encoding='utf-8') as f:
            st=time.strftime('%Y-%m-%dT%H:%M:%S')
            for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'適用: 除去巻(本番){len(clog)} / 更新ファイル{touched}(両環境) / backup {bak.name}',flush=True)

if __name__=='__main__': main()
