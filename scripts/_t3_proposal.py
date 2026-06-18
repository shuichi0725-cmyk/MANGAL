#!/usr/bin/env python3
"""
T3修正提案を「1作品=1行・平易」に整形(本番不変)。t3-consensus.tsv を集約。
各誤付与作について: 何を/どう直す/根拠(NDL著者・楽天題・正所有者) を読める形に。
出力: data/seeds/t3-proposal.tsv (人が見て検証する用) + 上位の物語形サンプルを表示。
"""
import sys,csv
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent

def main():
    rows=[]
    with open(ROOT/'data'/'seeds'/'t3-consensus.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r); rows=[x for x in r]
    # 列: shared_isbn,rk_title,ndl_title,ndl_author,owner_slug,owner_author,wrong_slug,wrong_author,wrong_vol,proposed_isbn,confidence
    byw=defaultdict(list)
    for x in rows: byw[x[6]].append(x)
    out=[]
    for wrong,xs in byw.items():
        hi=[x for x in xs if x[10]=='HIGH']
        lo=[x for x in xs if x[10]=='LOW']
        cf=[x for x in xs if x[10]=='CONFLICT']
        if not hi and not lo: continue  # HIGH/LOWのある誤付与のみ(CONFLICTのみは別扱い)
        # 代表(最頻のNDL著者/正所有者)
        from collections import Counter
        ndl_auth=Counter(x[3] for x in xs if x[3]).most_common(1)
        owner=Counter(x[4] for x in xs if x[4] and x[4]!='(所有者不明)').most_common(1)
        rk=Counter(x[1] for x in xs if x[1]).most_common(1)
        wrong_auth=Counter(x[7] for x in xs if x[7]).most_common(1)
        ndl_a=ndl_auth[0][0] if ndl_auth else ''
        owner_s=owner[0][0] if owner else '(所有者不明)'
        wa=wrong_auth[0][0] if wrong_auth else ''
        n_hi=len(hi); n_lo=len(lo)
        rk_t=rk[0][0] if rk else ''
        nani=f'除去すべきISBN {n_hi}巻' + (f'(＋要確認{n_lo})' if n_lo else '')
        dou=f'別作のISBN→「{wrong}」から除去。正所有者「{owner_s}」が保有'
        konkyo=f'NDL著者={ndl_a}(誤付与作の著者「{wa}」と不一致) / 楽天題={rk_t}'
        out.append([wrong,wa,nani,dou,owner_s,ndl_a,konkyo,n_hi,n_lo])
    out.sort(key=lambda z:-z[7])
    p=ROOT/'data'/'seeds'/'t3-proposal.tsv'
    with open(p,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t')
        w.writerow(['誤付与作品','誤の著者','何を','どう直す','正所有者','正の著者(NDL)','根拠','HIGH巻数','要確認巻数'])
        for r in out: w.writerow(r)
    print(f'修正提案: {len(out)} 作品 → {p}')
    print('\n=== 読みやすい形(上位8作) ===')
    for r in out[:8]:
        print(f'■ 誤付与作品: {r[0]}「{r[1]}」')
        print(f'   何を : {r[2]}')
        print(f'   どう : {r[3]}')
        print(f'   根拠 : {r[6]}')
        print(f'   信頼 : HIGH {r[7]}巻 / 要確認 {r[8]}巻\n')

if __name__=='__main__': main()
