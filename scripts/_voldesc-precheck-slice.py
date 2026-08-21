import sys, io, json
BATCH = sys.argv[1]
THRESH = int(sys.argv[2]) if len(sys.argv) > 2 else 44
SLICE = '.cache/voldesc/_slice.txt'
caps = {}
lines = io.open(SLICE, encoding='utf-8').read().split('\n')
for i, ln in enumerate(lines):
    if ln.startswith('#V '):
        isbn = ln.split('|')[-1].strip()
        caps[isbn] = lines[i+1].strip() if i+1 < len(lines) else ''
def lcr(a, b):
    if not a or not b: return 0, ''
    prev = [0]*(len(b)+1); best = 0; bi = 0
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1)
        ai = a[i-1]
        for j in range(1, len(b)+1):
            if ai == b[j-1]:
                cur[j] = prev[j-1] + 1
                if cur[j] > best: best = cur[j]; bi = i
        prev = cur
    return best, a[bi-best:bi]
n = 0; w = 0
for ln in io.open(BATCH, encoding='utf-8'):
    ln = ln.strip()
    if not ln: continue
    o = json.loads(ln)
    cap = caps.get(o['isbn13'])
    n += 1
    if not cap:
        print('NOCAP', o['isbn13'], o.get('slug'), 'v%s' % o.get('vol')); continue
    b, s = lcr(o['desc'], cap)
    if b >= THRESH:
        w += 1
        print('WARN', b, o.get('slug'), 'v%s' % o.get('vol'), ':', s)
print('checked %d, warn=%d' % (n, w))
