# -*- coding: utf-8 -*-
"""batch jsonl の desc と captions-cache の caption の最長共通部分列(連続)を測り、
40字以上のものを警告表示する(apply の 50字ゲートに落ちる前に自分で直すため)。"""
import io, json, sys, os

BATCH = sys.argv[1]
CACHE = '.cache/voldesc/captions-cache.jsonl'
THRESH = int(sys.argv[2]) if len(sys.argv) > 2 else 40

caps = {}
if os.path.exists(CACHE):
    for ln in io.open(CACHE, encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        i = o.get('isbn13') or o.get('isbn')
        c = (o.get('caption') or '') + ' ' + (o.get('contents') or '')
        if i:
            caps[i] = caps.get(i, '') + ' ' + c

def longest_common_run(a, b):
    # O(len(a)*len(b)) DP、descは短いので十分
    la, lb = len(a), len(b)
    prev = [0] * (lb + 1)
    best, bi = 0, 0
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        ai = a[i-1]
        for j in range(1, lb + 1):
            if ai == b[j-1]:
                cur[j] = prev[j-1] + 1
                if cur[j] > best:
                    best, bi = cur[j], i
        prev = cur
    return best, a[bi-best:bi]

bad = 0
for ln in io.open(BATCH, encoding='utf-8'):
    ln = ln.strip()
    if not ln:
        continue
    o = json.loads(ln)
    cap = caps.get(o['isbn13'], '')
    if not cap:
        continue
    n, s = longest_common_run(o['desc'], cap)
    if n >= THRESH:
        bad += 1
        print('WARN %d %s v%s : %s' % (n, o['slug'], o['vol'], s))
print('checked, warn=%d' % bad)
