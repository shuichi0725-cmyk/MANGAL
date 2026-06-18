#!/usr/bin/env python3
"""
マッド・ブル34 フラグメント統合(慎重・可逆)。
分裂15作(slug=数字, vol5-19, 集英社4-08-861)を canonical mad-buru-34 の standard に正巻番号で統合。
既存standardの 4-883-15(別版・楽天EMPTY)3巻は standardから除去(backup保全)。 分裂作はdrop+alias。
使い方: python _madbull_consolidate.py [--apply]
"""
import sys,io,csv,re,json,time,shutil
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def to13(s):
    s=str(s or '').replace('-','').strip(); return s if len(s)==13 and s.isdigit() else ''
def load(slug):
    fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
    return yaml.safe_load(fp.read_text(encoding='utf-8')) if fp.exists() else None

def main():
    can=load('mad-buru-34')
    std=[e for e in can['editions'] if e['type']=='standard'][0]
    # 既存: JC(4-08-861)は keep、それ以外(4-883-15)は strayへ
    keep=[]; stray=[]
    for v in std['volumes']:
        ib=to13(v.get('isbn13'))
        if ib.startswith('978408861'): keep.append(v)
        else: stray.append(v)
    # フラグメント(数字題,井上紀良,vol5-19)
    with open(ROOT/'data'/'seeds'/'audit-T4-volmismatch.tsv',encoding='utf-8-sig') as f:
        r=csv.reader(f,delimiter='\t'); next(r)
        frags={int(x[5]):x[0] for x in r if re.fullmatch(r'\d+',str(x[1]).strip())}
    fragvols=[]
    for n,slug in sorted(frags.items()):
        d=load(slug)
        if not d: continue
        vs=[v for e in d['editions'] for v in (e.get('volumes') or [])]
        if not vs: continue
        v=dict(vs[0]); v['number']=n   # 楽天巻番号に正す
        fragvols.append((slug,v))
    # 統合: keep(vol1-4) + fragvols(5-19)、 番号でdedup(fragment優先=JC連番)
    bynum={}
    for v in keep: bynum[v['number']]=v
    for slug,v in fragvols: bynum[v['number']]=v   # 上書き(JCブロック優先)
    newvols=[bynum[k] for k in sorted(bynum)]
    print('統合後 standard 巻:',sorted(bynum))
    print('除去するstray(4-883-15):',[(v['number'],v.get('isbn13')) for v in stray])
    print('drop予定の分裂作:',[s for s,_ in fragvols])
    if not APPLY:
        print('\n(dry-run)'); return
    bak=ROOT/'.cache'/f'madbull-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    std['volumes']=newvols
    out=yaml.dump(can,allow_unicode=True,sort_keys=False,default_flow_style=False)
    for base in ('data/manga.v2','.preview-data/manga'):
        p=ROOT/base/'mad-buru-34.yml'
        if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__mad-buru-34.yml')); p.write_text(out,encoding='utf-8')
    pv=ROOT/'.preview-data'/'manga'/'mad-buru-34.yml'
    if not pv.exists(): pv.write_text(out,encoding='utf-8')
    # 分裂作drop+alias
    alias={}; clog=[]
    for slug,_ in fragvols:
        alias[slug]='mad-buru-34'; clog.append({'dropped':slug,'canonical':'mad-buru-34','reason':'マッド・ブル34分裂統合'})
        for base in ('data/manga.v2','.preview-data/manga'):
            p=ROOT/base/f'{slug}.yml'
            if p.exists(): shutil.copy2(p,bak/(base.replace('/','_')+'__'+slug+'.yml')); p.unlink()
    af=ROOT/'data'/'seeds'/'dup-merge-alias.yml'
    cur=yaml.safe_load(af.read_text(encoding='utf-8')) if af.exists() else {}; cur=cur or {}; cur.update(alias)
    af.write_text(yaml.dump(cur,allow_unicode=True,sort_keys=True),encoding='utf-8')
    with (ROOT/'data'/'seeds'/'dup-merge-changelog.jsonl').open('a',encoding='utf-8') as f:
        st=time.strftime('%Y-%m-%dT%H:%M:%S')
        for r in clog: r['applied_at']=st; f.write(json.dumps(r,ensure_ascii=False)+'\n')
    # stray記録
    (ROOT/'data'/'seeds'/'madbull-stray-4883.json').write_text(json.dumps([{'number':v['number'],'isbn13':v.get('isbn13')} for v in stray],ensure_ascii=False),encoding='utf-8')
    print(f'適用: standard vol{len(newvols)} / 分裂drop {len(alias)} / stray記録3 / backup {bak.name}')

if __name__=='__main__': main()
