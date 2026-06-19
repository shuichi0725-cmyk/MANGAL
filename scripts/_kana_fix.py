#!/usr/bin/env python3
"""
kana不整合193の是正。多くは title_kana='正しいカナ|余計な漢字' 形式。
| 分割し最初の全カナ部分を採用(漢字junk除去)。slugは既に正しい読み側から出来てるので触らない。
- PIPE_STRIP: |前が全カナ → それを採用(安全自動)
- NEEDS_READING: 全カナ部分なし(=読み壊れ/私のrescue) → 別途(AI/NDL)。flagのみ
dry-run/--apply。 本番+preview。
"""
import sys,csv,re,unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT=Path(__file__).resolve().parent.parent
import yaml
APPLY='--apply' in sys.argv
def haskanji(s): return bool(re.search(r'[一-龯々]',str(s or '')))
def is_kana_ok(s):
    # 全カナ/ひらがな/長音/英数記号(漢字を含まない)
    return bool(s) and not haskanji(s)

def main():
    slugs=[x[0] for x in csv.reader(open(ROOT/'data'/'seeds'/'slug-kana-bug.tsv',encoding='utf-8-sig'),delimiter='\t') if x[0]!='slug']
    strip=[]; needs=[]
    for slug in slugs:
        fp=ROOT/'data'/'manga.v2'/f'{slug}.yml'
        if not fp.exists(): continue
        d=yaml.safe_load(fp.read_text(encoding='utf-8'))   # ★ymlから全文kana
        title=str(d.get('title') or ''); tk=str(d.get('title_kana') or '')
        parts=re.split(r'[|｜]',tk)
        cand=next((p.strip() for p in parts if is_kana_ok(p.strip()) and len(p.strip())>=2),'')
        if cand and cand!=tk:
            strip.append((slug,title,tk,cand))
        else:
            needs.append((slug,title,tk))
    print(f'193 → PIPE_STRIP(|前カナ採用=安全) {len(strip)} / NEEDS_READING(読み要) {len(needs)}')
    print('-- PIPE_STRIP サンプル --')
    for s,t,old,new in strip[:15]: print(f'  {s[:22]:22s}「{t[:14]}」 {old[:18]} → {new[:16]}')
    print('-- NEEDS_READING サンプル --')
    for s,t,old in needs[:12]: print(f'  {s[:22]:22s}「{t[:14]}」 kana={old[:18]}')
    (ROOT/'data'/'seeds'/'kana-needs-reading.tsv').write_text(
        'slug\ttitle\tcurrent_kana\n'+'\n'.join(f'{s}\t{t}\t{o}' for s,t,o in needs),encoding='utf-8')
    if not APPLY:
        print('\n(dry-run。 --applyでPIPE_STRIP適用)'); return
    import time,shutil,json
    bak=ROOT/'.cache'/f'kanafix-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True,exist_ok=True)
    lf=(ROOT/'data'/'seeds'/'kana-fix-changelog.jsonl').open('a',encoding='utf-8'); st=time.strftime('%Y-%m-%dT%H:%M:%S')
    n=0
    for slug,title,old,new in strip:
        for base in ('data/manga.v2','.preview-data/manga'):
            fp=ROOT/base/f'{slug}.yml'
            if not fp.exists(): continue
            d=yaml.safe_load(fp.read_text(encoding='utf-8'))
            if d.get('title_kana')==old:
                shutil.copy2(fp,bak/(base.replace('/','_')+'__'+slug+'.yml'))
                d['title_kana']=new
                fp.write_text(yaml.dump(d,allow_unicode=True,sort_keys=False,default_flow_style=False),encoding='utf-8')
                if base=='data/manga.v2': n+=1; lf.write(json.dumps({'slug':slug,'old':old,'new':new,'at':st},ensure_ascii=False)+'\n')
    lf.close()
    print(f'\n適用: {n}作のtitle_kana是正(漢字junk除去)。 backup={bak}')

if __name__=='__main__': main()
