#!/usr/bin/env python3
"""
ISBN集合EXACT複製のうち同一著者(=真の題違い複製)をdedup。canonical=最多巻(tie→短title→短slug)。
他slug→alias+削除。別著者(誤ISBN共有)はflagのみ(un-merge要)。 dry-run/--apply。
"""
import sys,csv,os,re,unicodedata,time,shutil,json
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def na(s): return re.sub(r'[\s　・。.]','',unicodedata.normalize('NFKC',str(s or ''))).lower()
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    if not fp.exists(): return None
    d=yaml.safe_load(fp.read_text(encoding='utf-8'))
    return {'d':d,'title':str(d.get('title','')),'n':sum(len(e.get('volumes',[])) for e in d.get('editions',[])),
            'au':set(na(a.get('name')) for a in (d.get('authors') or []))}
def main():
    dedup=[]; flag=[]
    for x in csv.reader(open(ROOT/'data'/'seeds'/'isbn-set-dup.tsv',encoding='utf-8-sig'),delimiter='\t'):
        if x[0]!='EXACT(完全複製)': continue
        slugs=[s.strip() for s in x[1].split('|')]
        infos={s:load(s) for s in slugs}; infos={s:i for s,i in infos.items() if i}
        if len(infos)<2: continue
        aus=[infos[s]['au'] for s in infos]
        shared=set.intersection(*aus) if all(aus) else set()
        if not shared: flag.append(('別著者',slugs)); continue
        canon=sorted(infos,key=lambda s:(-infos[s]['n'],len(infos[s]['title']),len(s)))[0]
        dups=[s for s in infos if s!=canon]
        # 題が変種関係(canonicalを含む/共通2字stem)かチェック。全dupが満たす時だけdedup
        def tnorm(t): return re.sub(r'[\s　・:：，,。．\-ー~〜!！?？&＆/+（）()【】「」]','',unicodedata.normalize('NFKC',t))
        ct=tnorm(infos[canon]['title'])
        def variant(dt):
            dt=tnorm(dt)
            if not dt or not ct: return False
            if ct in dt or dt in ct: return True
            # 2字以上の共通連続部分
            for i in range(len(ct)-1):
                if ct[i:i+2] in dt: return True
            return False
        if all(variant(infos[s]['title']) for s in dups):
            dedup.append((canon,dups,infos))
        else:
            flag.append(('題相違',slugs))
    print(f'同一著者dedup: {len(dedup)}グループ / 別著者flag: {len(flag)}')
    for canon,dups,infos in dedup:
        ti=infos[canon]['title'][:12]; cn=infos[canon]['n']
        print('  keep '+canon+'「'+ti+'」('+str(cn)+') ← '+str(len(dups))+'複製: '+str(dups[:4]))
    if not APPLY:
        print('\n(dry-run。 --applyで dedup)'); return
    bak=ROOT/'.cache'/f'isbndup-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'; alias=yaml.safe_load(af.read_text(encoding='utf-8')) or {}
    lf=(ROOT/'data'/'seeds'/'isbn-dup-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S'); n=0
    for canon,dups,infos in dedup:
        for dup in dups:
            alias[dup]=canon
            for base in ('data/manga.v2','.preview-data/manga'):
                f2=ROOT/base/f'{dup}.yml'
                if f2.exists(): shutil.copy2(f2,bak/(base.replace('/','_')+'__'+dup+'.yml')); f2.unlink()
            lf.write(json.dumps({'dup':dup,'canon':canon,'at':st},ensure_ascii=False)+'\n'); n+=1
    af.write_text(yaml.dump(alias,allow_unicode=True,sort_keys=True),encoding='utf-8'); lf.close()
    (ROOT/'data'/'seeds'/'isbn-dup-unmerge-flag.tsv').write_text('\n'.join(r+'\t'+' | '.join(ss) for r,ss in flag),encoding='utf-8')
    print(f'\ndedup適用: {n}複製削除 / {len(dedup)}グループ→canonical。別著者{len(flag)}はflag(un-merge要)。backup={bak}')

if __name__=='__main__': main()
