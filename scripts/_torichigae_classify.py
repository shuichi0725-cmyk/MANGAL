#!/usr/bin/env python3
"""
CREATE_NEW 152 を A/B/C に仕分け(読み取りのみ・本番不変)。
A = 国内・著者日本語・巻題がシリーズで揃う・楽天data有 → 自動作成
B = scope外(著者がラテン/西洋名=外国コミック疑い・非漫画) → 保全せず削除のみ
C = 題がシリーズ化不可(巻ごと別題=アンソロ/翻訳短編)or 楽天data薄 → 退避(後日手動)
出力: data/seeds/torichigae-class.tsv
"""
import sys,csv,re,json,unicodedata
from pathlib import Path
from collections import defaultdict
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def zen(s): return str(s).translate(str.maketrans('０１２３４５６７８９','0123456789'))
def stripvol(s):
    s=zen(unicodedata.normalize('NFKC',str(s or ''))); s=re.sub(r'[（(〈\[【].*?[）)〉\]】]','',s)
    s=re.sub(r'\s*(第)?\d+\s*(巻|集)?\s*$','',s); return re.sub(r'[\s　]','',s).strip()
def is_latin(s):
    s=unicodedata.normalize('NFKC',str(s or '')).strip()
    return bool(s) and bool(re.fullmatch(r'[A-Za-z0-9 .,&\'\-]+',s))
WESTERN=['シュルツ','デーヴィス','デイビス','スピーゲルマン','ヤンソン','ニー','エルジェ','ゴシニ','ユデルゾ','チャールズ','トーベ','ミシェル','ミッシェル']
def lcp(strs):
    if not strs: return ''
    s1=min(strs); s2=max(strs); n=0
    while n<len(s1) and n<len(s2) and s1[n]==s2[n]: n+=1
    return s1[:n]

def main():
    targets=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'torichigae-plan.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]=='label_slug' or not x[9].startswith('CREATE_NEW'): continue
        targets.append((x[0],x[5],x[6]))   # label_slug, 真題, 真著
    wrong=defaultdict(set)
    def aset(s): return set(re.sub(r'[（(].*?[）)]|[\s　・。.]','',re.sub(r'[ぁ-ん]',lambda m:chr(ord(m.group())+0x60),unicodedata.normalize('NFKC',x))).lower() for x in re.split(r'[;／/、,]',s) if x.strip())
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-source-table.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if len(x)<7 or x[6]!='TORICHIGAE' or (aset(x[3]) & aset(x[5])): continue
        wrong[x[1]].add(x[0])
    rk={}
    for line in (ROOT/'.cache'/'rakuten-isbn.jsonl').open(encoding='utf-8'):
        try: o=json.loads(line); ib=to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
        except: continue
        if ib and o.get('item'): rk[ib]=o['item']
    rows=[]; cnt=defaultdict(int)
    for slug,tt,ta in targets:
        isbns=sorted(wrong[slug])
        vtitles=[stripvol(rk[ib].get('title')) for ib in isbns if ib in rk and rk[ib].get('title')]
        n_rk=len(vtitles)
        # 著者外国判定
        foreign = is_latin(ta) or any(w in ta for w in WESTERN)
        # 巻題の一貫性(共通prefix)
        stem=lcp(vtitles) if vtitles else ''
        consistent = len(stem)>=2 and n_rk>=max(1,len(isbns)//2)
        if foreign:
            cls='B_SCOPE外'
        elif n_rk==0:
            cls='C_楽天data無'
        elif consistent:
            cls='A_自動作成'
        else:
            cls='C_題不一致'
        cnt[cls]+=1
        rows.append([slug,tt[:16],ta[:14],len(isbns),n_rk,stem[:12],cls])
    out=ROOT/'data'/'seeds'/'torichigae-class.tsv'
    with open(out,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(['label_slug','真題','真著','誤ISBN','楽天有巻','共通stem','分類'])
        for r in sorted(rows,key=lambda z:(z[6],-z[3])): w.writerow(r)
    print('=== A/B/C 仕分け ===')
    for k in sorted(cnt): print(f'  {k}: {cnt[k]}')
    print(f'  → {out}')
    for tag in ('A_自動作成','B_SCOPE外','C_題不一致','C_楽天data無'):
        ex=[r for r in rows if r[6]==tag][:6]
        print(f'-- {tag} --')
        for r in ex: print(f'  {r[0][:22]:22s} 真「{r[1][:12]}」by {r[2][:10]} {r[3]}巻(楽天{r[4]}) stem「{r[5]}」')

if __name__=='__main__': main()
