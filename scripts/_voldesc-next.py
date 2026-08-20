# -*- coding: utf-8 -*-
"""巻説明: par/par-old のジョブから「未生成の巻」を N 件ぶん取り出して表示する。
seed済み + out/*.jsonl に既出 の ISBN は除外(=実質cursor)。"""
import io, json, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
done = set()
for ln in io.open(os.path.join(ROOT,'data','seeds','volume-desc-ja.jsonl'), encoding='utf-8'):
    ln = ln.strip()
    if ln:
        try: done.add(str(json.loads(ln)['isbn13']))
        except Exception: pass
SKIPF = os.path.join(ROOT,'.cache','voldesc','g6k-skip.txt')
if os.path.exists(SKIPF):
    for ln in io.open(SKIPF, encoding='utf-8'):
        ln = ln.strip()
        if ln: done.add(ln)
for p in glob.glob(os.path.join(ROOT,'.cache','voldesc','out','*.jsonl')):
    for ln in io.open(p, encoding='utf-8'):
        ln = ln.strip()
        if ln:
            try: done.add(str(json.loads(ln)['isbn13']))
            except Exception: pass
files = sorted(glob.glob(os.path.join(ROOT,'.cache','voldesc','par','*.txt'))) + \
        sorted(glob.glob(os.path.join(ROOT,'.cache','voldesc','par-old','*.txt')))
n = 0
for p in files:
    txt = io.open(p, encoding='utf-8').read()
    m = re.match(r'SERIES slug=(\S+)\s+title=(.*)', txt)
    slug = m.group(1) if m else os.path.basename(p)[:-4]
    title = m.group(2).strip() if m else ''
    blocks = re.findall(r'--- vol (\S+)\s+isbn13 (\d{13})\n(.*?)(?=\n--- vol |\Z)', txt, re.S)
    keep = [(v,i,c.strip()) for v,i,c in blocks if i not in done]
    if not keep: continue
    print('##SERIES %s | %s' % (slug, title))
    for v,i,c in keep:
        print('#V %s | %s\n%s' % (v, i, c))
        n += 1
        if n >= N: break
    if n >= N: break
print('##COUNT %d' % n)
