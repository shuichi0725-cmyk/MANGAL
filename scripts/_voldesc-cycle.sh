#!/bin/sh
# usage: _voldesc-cycle.sh <NNN> <commit-msg-count>
N=$1
CNT=$2
cd "C:/Users/chiba shuichi/code/MANGAL" || exit 1
if [ -f ".cache/voldesc/out/g6k-${N}b.jsonl" ]; then
  PYTHONIOENCODING=utf-8 python -c "
import io,json,sys
n=sys.argv[1]
bad=set()
for ln in io.open('.cache/voldesc/out/g6k-%sb.jsonl'%n,encoding='utf-8'):
    ln=ln.strip()
    if ln: bad.add(json.loads(ln)['isbn13'])
out=[]
for ln in io.open('.cache/voldesc/out/g6k-%s.jsonl'%n,encoding='utf-8'):
    ln=ln.strip()
    if not ln: continue
    if json.loads(ln)['isbn13'] in bad: continue
    out.append(ln)
io.open('.cache/voldesc/out/g6k-%sa.jsonl'%n,'w',encoding='utf-8').write('\n'.join(out)+'\n')
" "$N"
  PYTHONIOENCODING=utf-8 python scripts/_voldesc-apply.py ".cache/voldesc/out/g6k-${N}a.jsonl" >/dev/null 2>&1
  PYTHONIOENCODING=utf-8 python scripts/_voldesc-apply.py ".cache/voldesc/out/g6k-${N}b.jsonl" >/dev/null 2>&1
else
  PYTHONIOENCODING=utf-8 python scripts/_voldesc-apply.py ".cache/voldesc/out/g6k-${N}.jsonl" >/dev/null 2>&1
fi
PYTHONIOENCODING=utf-8 python -c "
import io,json,os,sys
n=sys.argv[1]
seed=set()
for ln in io.open('data/seeds/volume-desc-ja.jsonl',encoding='utf-8'):
    try: seed.add(json.loads(ln)['isbn13'])
    except: pass
for suf in ('','a','b'):
    p='.cache/voldesc/out/g6k-%s%s.jsonl'%(n,suf)
    if suf=='' and os.path.exists('.cache/voldesc/out/g6k-%sa.jsonl'%n): continue
    if not os.path.exists(p): continue
    for ln in io.open(p,encoding='utf-8'):
        ln=ln.strip()
        if not ln: continue
        o=json.loads(ln)
        if o['isbn13'] not in seed: print('REJ',o['isbn13'],o['slug'],o['vol'])
" "$N"
PYTHONIOENCODING=utf-8 python scripts/_voldesc-next.py 90 > .cache/voldesc/_slice.txt 2>&1
wc -l data/seeds/volume-desc-ja.jsonl
git add data/seeds/volume-desc-ja.jsonl && git commit -q -m "巻説明 +約${CNT}件(volume-desc)" && git push -q origin claude/manga-database-affiliate-3x0ms && echo PUSHED
