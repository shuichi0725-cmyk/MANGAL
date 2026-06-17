#!/usr/bin/env python3
"""
特装版混入 修正(a) 適用 = special-edition-fix.yml を本番/テストの manga 群に反映。
案B: standard版の該当巻を「通常版ISBN/書影/発売日」に差替え、特装版を variant 併存(捨てない)。

履歴(git追跡): data/seeds/special-edition-fix.yml(修正定義) + data/seeds/special-edition-fix-changelog.jsonl(実変更ログ)。
安全策: 変更ファイルのみ .cache にバックアップ。 special_isbn一致で冪等(再実行で二重化しない)。

使い方: python _special_edition_fix_apply.py <mangaDir>   (例: data/manga.v2 / .preview-data/manga)
        --dry-run で集計のみ。
"""
import json,sys,io,time,shutil,subprocess
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
try: from yaml import CSafeLoader as Loader
except: from yaml import SafeLoader as Loader

def to13(s):
    s=str(s or '').replace('-','').strip()
    return s if (len(s)==13 and s.isdigit()) else s

DRY='--dry-run' in sys.argv
args=[a for a in sys.argv[1:] if not a.startswith('--')]
MDIR=Path(args[0]) if args else ROOT/'data'/'manga.v2'

def seed_path():
    for i,a in enumerate(sys.argv):
        if a=='--seed' and i+1<len(sys.argv):
            return ROOT/sys.argv[i+1] if not Path(sys.argv[i+1]).is_absolute() else Path(sys.argv[i+1])
    return ROOT/'data'/'seeds'/'special-edition-fix.yml'

def main():
    doc=yaml.safe_load(seed_path().read_text(encoding='utf-8'))
    bym={to13(x['special_isbn']):x for x in doc['corrections']}
    # special isbn 一覧で候補ファイルを rg 抽出(高速)
    tmp=ROOT/'.cache'/'sef-special-isbns.txt'
    tmp.write_text('\n'.join(bym.keys()),encoding='utf-8')
    try:
        out=subprocess.run(['rg','-l','-F','-f',str(tmp),str(MDIR)],capture_output=True,text=True,timeout=600)
        files=[Path(p) for p in out.stdout.splitlines() if p.strip()]
    except Exception as e:
        print('rg失敗→全走査',e); files=list(MDIR.glob('*.yml'))
    print(f'{MDIR}: 候補 {len(files)} ファイル{" [DRY]" if DRY else ""}',flush=True)

    bak=None
    if not DRY:
        bak=ROOT/'.cache'/f'manga.bak-sef-{time.strftime("%Y%m%d-%H%M%S")}-{MDIR.name}'
        bak.mkdir(parents=True,exist_ok=True)
    clog=[]
    n_vol=0; n_file=0; cover_set=0; cover_null=0
    for fp in files:
        raw=fp.read_text(encoding='utf-8')
        hdr=raw.split('\n',1)[0] if raw.startswith('#') else None
        d=yaml.load(raw,Loader=Loader)
        if not isinstance(d,dict): continue
        slug=d.get('slug'); changed=False
        for e in (d.get('editions') or []):
            if e.get('type')!='standard': continue
            for v in (e.get('volumes') or []):
                cur=to13(v.get('isbn13'))
                c=bym.get(cur)
                if not c: continue
                if not c.get('normal_cover'):   # 通常版書影が無い分は今回は適用せず保留(空タイル回避)
                    cover_null+=1; continue
                # 差替え
                v['isbn13']=c['normal_isbn']
                v['cover_url']=c['normal_cover']; cover_set+=1
                if c.get('normal_date'): v['release_date']=c['normal_date']
                var=dict(c['variant'])
                v['variants']=[{k:var.get(k) for k in ('label','isbn13','cover_url','price')}]
                changed=True; n_vol+=1
                clog.append({'slug':slug,'number':v.get('number'),'special_isbn':cur,
                             'normal_isbn':c['normal_isbn'],'version':var.get('label'),
                             'normal_cover':bool(c.get('normal_cover'))})
        if changed:
            n_file+=1
            if not DRY:
                shutil.copy2(fp,bak/fp.name)
                buf=io.StringIO()
                if hdr: buf.write(hdr+'\n')
                yaml.dump(d,buf,allow_unicode=True,sort_keys=False,default_flow_style=False)
                fp.write_text(buf.getvalue(),encoding='utf-8')

    if not DRY and clog:
        cl=ROOT/'data'/'seeds'/'special-edition-fix-changelog.jsonl'
        with cl.open('a',encoding='utf-8') as f:
            stamp=time.strftime('%Y-%m-%dT%H:%M:%S')
            for r in clog:
                r['applied_at']=stamp; r['target']=MDIR.name
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(f'差替え 巻 {n_vol} / ファイル {n_file} / 通常書影セット {cover_set} / 書影null {cover_null}',flush=True)
    if not DRY: print(f'backup → {bak}\nchangelog → data/seeds/special-edition-fix-changelog.jsonl',flush=True)

if __name__=='__main__': main()
