#!/usr/bin/env python3
"""
取り違え是正の【計画表】(読み取りのみ・本番不変)。option2=ラベル維持+中身入替、ただし削除巻を失わない。
各取り違え作について判定:
- 誤ISBNが他作にも在る → DELETE(消すだけ・保全済)
- 真の作品がDBに既存(題+著者一致) → MOVE(その作へ移送)
- どこにも無い → CREATE_NEW(新規フォルダ作成して保全)
- ラベル側が空化 → RE_ISBN(ラベルの本物巻を別途再構築)
出力: data/seeds/torichigae-plan.tsv
"""
import sys,csv,re,unicodedata
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as L
except: from yaml import SafeLoader as L
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def hk(s): return re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),s)
def tcore(s):
    s=zen(str(s or '')); s=unicodedata.normalize('NFKC',s); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'[．.]\s*\d+\s*$','',s); s=re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+]','',s).lower()
    return hk(s)
def norm1(p):
    p=unicodedata.normalize('NFKC',p); p=re.sub(r'[（(].*?[）)]','',p)
    p=re.sub(r'^(team|チーム)','',p,flags=re.I); p=re.sub(r'[\s　・。.\]\[]','',p)
    return hk(p).lower()
def aset(s): return set(norm1(x) for x in re.split(r'[;／/、,]',s) if len(norm1(x))>=2)
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''

def main():
    wrong=defaultdict(set); truen={}; labelinfo={}
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-source-table.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if len(x)<7 or x[6]!='TORICHIGAE': continue
        if aset(x[3]) & aset(x[5]): continue
        wrong[x[1]].add(x[0]); truen[x[0]]=(x[4],x[5]); labelinfo[x[1]]=(x[2],x[3])
    print(f'取り違え作 {len(wrong)} / 誤ISBN {sum(len(v) for v in wrong.values())} [DB scan]',flush=True)
    # DB全体: isbn->slugs, 各slug巻数, title_core+author 索引
    isbn2slugs=defaultdict(set); slug_total=defaultdict(int); titidx=defaultdict(list)
    for i,fp in enumerate(sorted((ROOT/'data'/'manga.v2').glob('*.yml'))):
        if i%20000==0 and i: print(f'  scan {i}',flush=True)
        try: d=yaml.load(fp.read_text(encoding='utf-8'),Loader=L)
        except: continue
        if not isinstance(d,dict): continue
        sl=d.get('slug'); tc=tcore(d.get('title'))
        au=set()
        for k in ('authors','original_authors'):
            for a in (d.get(k) or []):
                nm=a.get('name') if isinstance(a,dict) else a
                au|=aset(str(nm))
        titidx[tc].append((sl,au))
        for e in (d.get('editions') or []):
            for v in (e.get('volumes') or []):
                slug_total[sl]+=1
                ib=to13(v.get('isbn13'))
                if ib: isbn2slugs[ib].add(sl)
    rows=[]
    for slug,isbns in sorted(wrong.items(),key=lambda kv:-len(kv[1])):
        lt,la=labelinfo[slug]
        tt,ta=truen[next(iter(isbns))]
        n=len(isbns)
        n_else=sum(1 for ib in isbns if (isbn2slugs[ib]-{slug}))
        empties = slug_total[slug]-n<=0
        # 真の作品がDBに既存? (真題core + 真著者一致, 自分以外)
        tta=aset(ta); cand=[s for s,a in titidx.get(tcore(tt),[]) if s!=slug and (not tta or (a & tta))]
        true_in_db = cand[0] if cand else ''
        if n_else==n:
            action='DELETE(全て他作に在り=消すだけ)'
        elif true_in_db:
            action=f'MOVE→{true_in_db}(真作既存)'
        else:
            action='CREATE_NEW(真作をDBに新規作成して保全)'
        if empties: action+=' +RE_ISBN(ラベル本物要)'
        rows.append([slug,lt,la,n,n_else,str(tt)[:18],ta[:14],true_in_db,'空' if empties else '',action])
    out=ROOT/'data'/'seeds'/'torichigae-plan.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['label_slug','label_title','label_author','誤ISBN','他在数','真題','真著','真作slug(既存)','空化','計画'])
        for r in rows: w.writerow(r)
    from collections import Counter
    ac=Counter(re.split(r'[(→ ]',r[9])[0] for r in rows)
    print(f'\n=== 計画サマリ ({len(rows)}作) ===')
    for k,v in ac.most_common(): print(f'  {k}: {v}')
    nnew=sum(1 for r in rows if r[9].startswith('CREATE_NEW')); nmove=sum(1 for r in rows if 'MOVE' in r[9]); ndel=sum(1 for r in rows if r[9].startswith('DELETE'))
    print(f'  → CREATE_NEW {nnew} / MOVE {nmove} / DELETE {ndel}')
    print(f'  → {out}')
    print('-- サンプル --')
    for r in rows[:16]: print(f'  {r[0][:20]:20s}「{r[1][:10]}」誤{r[3]}(他在{r[4]}) 真「{r[5][:10]}」{r[6][:8]} → {r[9][:34]}')

if __name__=='__main__': main()
