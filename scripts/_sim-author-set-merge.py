"""【dry-run sim / 本番不変】著者集合+正規化title による series 統合提案を生成。

種2 sqlite 不変・種3 不変・series-merge.yml も書き換えない。
提案を .cache/proposed-author-set-merges.json / .csv に出力するだけ。

ロジック:
  group key = (frozenset(series_authors.mangaka_id), norm_title(title))
  - 同 group 内 2+ series = 分裂作品 候補
  - semantic subtitle (第/部/編/外伝 等) を含む混在 group は 保留 (= 別ページ維持が正当)
  - それ以外は auto 統合候補。main = 最多巻数 sid。
"""
from __future__ import annotations
import csv, json, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
DB=Path('.cache/db-v2.sqlite')

def norm_title(t): return re.sub(r'[・\s　：:，、。.\-―ー~〜!！?？／/]+','',t or '')
SEMANTIC=['第','部','編','外伝','前編','後編','番外','スピンオフ','SEASON','season','Part','PART','章','完結','SEASON']
def is_semantic_sub(s):
    return bool(s) and any(m in s for m in SEMANTIC)

def main():
    con=sqlite3.connect(DB); c=con.cursor()
    auth=defaultdict(set)
    for sid,mid in c.execute('select series_id,mangaka_id from series_authors'): auth[sid].add(mid)
    volc=defaultdict(int)
    for sid,n in c.execute('select e.series_id,count(*) from editions e join volumes v on v.edition_id=e.id group by e.series_id'): volc[sid]=n
    rows=c.execute('select id,title,subtitle,qid,series_key from series').fetchall()
    grp=defaultdict(list)
    for sid,t,s,q,sk in rows:
        a=frozenset(auth.get(sid,()))
        if not a: continue
        grp[(a,norm_title(t))].append({'sid':sid,'title':t,'sub':s,'qid':q,'key':sk,'vols':volc[sid]})
    auto=[]; held=[]
    for (a,nt),v in grp.items():
        if len({m['sid'] for m in v})<2: continue
        has_sem=any(is_semantic_sub(m['sub']) for m in v)
        nonsem={m['sid'] for m in v if not is_semantic_sub(m['sub'])}
        rec={'norm_title':nt,'n_authors':len(a),'members':sorted(v,key=lambda m:-m['vols'])}
        rec['main_sid']=rec['members'][0]['sid']
        rec['total_vols']=sum(m['vols'] for m in v)
        rec['distinct_qids']=sorted({m['qid'] for m in v if m['qid']})
        if has_sem and len(nonsem)<len({m['sid'] for m in v}):
            held.append(rec)
        else:
            auto.append(rec)
    auto.sort(key=lambda r:-r['total_vols']); held.sort(key=lambda r:-r['total_vols'])
    Path('.cache').mkdir(exist_ok=True)
    json.dump({'auto_merge':auto,'held':held,
        'summary':{'auto_groups':len(auto),'auto_series':sum(len(r['members']) for r in auto),
                   'sid_reduction':sum(len(r['members'])-1 for r in auto),
                   'held_groups':len(held)}},
        open('.cache/proposed-author-set-merges.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    with open('.cache/proposed-author-set-merges.csv','w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['kind','main_sid','total_vols','n_member_sids','distinct_qids','titles','member_sids'])
        for kind,lst in (('auto',auto),('held',held)):
            for r in lst:
                w.writerow([kind,r['main_sid'],r['total_vols'],len(r['members']),
                    '|'.join(r['distinct_qids']),
                    ' / '.join(sorted({m['title'] for m in r['members']})),
                    ','.join(str(m['sid']) for m in r['members'])])
    s={'auto_groups':len(auto),'auto_series':sum(len(r['members']) for r in auto),
       'sid_reduction':sum(len(r['members'])-1 for r in auto),'held_groups':len(held)}
    print('proposed merges written:')
    print(f"  auto_merge groups : {s['auto_groups']:,}  (series {s['auto_series']:,} → {s['auto_groups']:,})")
    print(f"  sid reduction     : {s['sid_reduction']:,}")
    print(f"  held (manual)     : {s['held_groups']:,}")
    print('  .cache/proposed-author-set-merges.json / .csv')

if __name__=='__main__': main()
