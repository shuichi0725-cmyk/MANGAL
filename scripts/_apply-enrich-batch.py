# -*- coding: utf-8 -*-
"""エンリッチ生成物(data/enrich-out-2026-07/batch-NNNN.json)を seed へ純粋追加。

skill enrich-catch-synopsis の 2026-07-28 字数規格に準拠:
  キャッチ 50-70字 / 詳細 80-110字。
ゲート:
  (a) 字数 (b) 本番manga.v2に既存の項目は書かない(空欄fillのみ)
  (c) caption丸写し検出(8gram) (d) catch==synopsis の短長2種化を禁止
  (e) genre は master32(data/genres.yml) 検証 + 既存genre在りには書かない

usage: python scripts/_apply-enrich-batch.py 0191 0192 [--apply]
       python scripts/_apply-enrich-batch.py 0191 --requeue [--apply]   # 短キャッチ再生成分=上書き許可
"""
import json, os, shutil, sys, re, html, datetime
import yaml
try: from yaml import CSafeLoader as L
except Exception: from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, 'data', 'enrich-out-2026-07')
BATCHDIR = os.path.join(ROOT, '.cache', 'enrich-batches')

APPLY = '--apply' in sys.argv
REQUEUE = '--requeue' in sys.argv
NS = [a for a in sys.argv[1:] if not a.startswith('--')]
if not NS:
    print('usage: _apply-enrich-batch.py <NNNN> [...] [--apply] [--requeue]'); sys.exit(1)

CATCH_MIN, CATCH_MAX = 48, 74      # 規格50-70 ±2
SYN_MIN, SYN_MAX = 78, 114         # 規格80-110 ±4
BLOCK, WARN = 0.55, 0.40

MASTER = set((yaml.safe_load(open(os.path.join(ROOT, 'data', 'genres.yml'), encoding='utf-8')) or {}).get('genres', {}).keys())
if not MASTER:  # 別形式(list)対応
    g = yaml.safe_load(open(os.path.join(ROOT, 'data', 'genres.yml'), encoding='utf-8'))
    if isinstance(g, list):
        MASTER = {x['key'] if isinstance(x, dict) else x for x in g}

def prod(slug):
    p = os.path.join(ROOT, 'data', 'manga.v2', slug + '.yml')
    if not os.path.exists(p): return None
    try: d = yaml.load(open(p, encoding='utf-8'), Loader=L) or {}
    except Exception: return {}
    return {'catch': bool((d.get('catch') or '').strip()),
            'syn': bool((d.get('synopsis') or '').strip()),
            'genres': list(d.get('genres') or [])}

def ngram_overlap(a, b, k=8):
    a = re.sub(r'\s', '', a); b = re.sub(r'\s', '', b)
    if len(a) < k or len(b) < k: return 0.0
    bs = {b[i:i+k] for i in range(len(b)-k+1)}
    hit = sum(1 for i in range(len(a)-k+1) if a[i:i+k] in bs)
    return hit / max(1, (len(a)-k+1))

out = {}; capmap = {}
for n in NS:
    p = os.path.join(OUTDIR, f'batch-{n}.json')
    d = json.load(open(p, encoding='utf-8'))
    for s, v in d.items():
        out[s] = v
    bp = os.path.join(BATCHDIR, f'batch-{n}.json')
    if os.path.exists(bp):
        bd = json.load(open(bp, encoding='utf-8'))
        for e in (bd['items'] if isinstance(bd, dict) else bd):
            capmap[e['slug']] = [html.unescape(c.get('caption') or '') for c in (e.get('captions') or [])]

bad = []; block = []; warn = []
for s, v in out.items():
    c = (v.get('catch') or '').strip(); y = (v.get('synopsis') or '').strip()
    ga = v.get('genres_add') or []
    st = prod(s)
    if st is None: bad.append((s, 'NOFILE')); continue
    if c and not (CATCH_MIN <= len(c) <= CATCH_MAX): bad.append((s, f'catch{len(c)}'))
    if y and not (SYN_MIN <= len(y) <= SYN_MAX): bad.append((s, f'syn{len(y)}'))
    if c and y and (c[:20] == y[:20]): bad.append((s, 'catch==syn頭20字'))
    for g in ga:
        if g not in MASTER: bad.append((s, f'genre外:{g}'))
    if len(ga) > 4: bad.append((s, f'genre{len(ga)}個'))
    if y and not (st.get('syn') and not REQUEUE):
        m = max([ngram_overlap(y, cap) for cap in capmap.get(s, [])] or [0])
        if m >= BLOCK: block.append((round(m, 2), s))
        elif m >= WARN: warn.append((round(m, 2), s))
if bad:
    print('VIOLATIONS', len(bad))
    for x in bad: print('  ', x)
    sys.exit(1)
if warn:
    warn.sort(reverse=True); print(f'△言い換え要検討 {len(warn)}件:', warn[:12])
if block:
    block.sort(reverse=True)
    print(f'★丸写しblock(>={BLOCK}) {len(block)}件 → 言い換えてから再実行:')
    for x in block: print('  ', x)
    sys.exit(2)
print(f'validated {len(out)} entries OK')

paths = {'catch': os.path.join(ROOT, 'data', 'seeds', 'catch-ja.json'),
         'syn':   os.path.join(ROOT, 'data', 'seeds', 'synopsis-slug-ja.json'),
         'genre': os.path.join(ROOT, 'data', 'seeds', 'genre-enrich-2425.json'),
         'cidx':  os.path.join(ROOT, 'data', 'manga-catch-index.json')}
catch = json.load(open(paths['catch'], encoding='utf-8'))
syn = json.load(open(paths['syn'], encoding='utf-8'))
genre = json.load(open(paths['genre'], encoding='utf-8'))
cidx = json.load(open(paths['cidx'], encoding='utf-8'))

ac = asn = ag = ai = 0
ov_c = ov_s = 0
skip_catch = skip_syn = skip_genre = 0
changed = []
for s, v in out.items():
    st = prod(s) or {}
    c = (v.get('catch') or '').strip(); y = (v.get('synopsis') or '').strip()
    ga = v.get('genres_add') or []
    touched = False
    if c:
        if REQUEUE:
            if catch.get(s) != c: catch[s] = c; cidx[s] = c; ov_c += 1; touched = True
        elif st.get('catch'): skip_catch += 1
        else:
            if s not in catch: catch[s] = c; ac += 1; touched = True
            if not cidx.get(s): cidx[s] = c; ai += 1
    if y:
        if REQUEUE:
            if syn.get(s) != y: syn[s] = y; ov_s += 1; touched = True
        elif st.get('syn'): skip_syn += 1
        else:
            if s not in syn: syn[s] = y; asn += 1; touched = True
    if ga:
        if st.get('genres'): skip_genre += 1
        elif s not in genre: genre[s] = ga; ag += 1; touched = True
    if touched: changed.append(s)

mode = 'REQUEUE(上書き許可)' if REQUEUE else '純粋追加'
print(f'[{mode}] catch+{ac} / syn+{asn} / genre+{ag} / catch索引+{ai}'
      + (f' / 上書き catch{ov_c}・syn{ov_s}' if REQUEUE else '')
      + f'  (本番既済skip: catch{skip_catch}/syn{skip_syn}/genre{skip_genre})')
print(f'変更slug {len(changed)}件')
if not APPLY:
    print('(dry-run)'); sys.exit()

stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
for k, p in paths.items():
    shutil.copy2(p, os.path.join(ROOT, '.cache', os.path.basename(p) + f'.bak-enrich{stamp}'))
json.dump(catch, open(paths['catch'], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(syn, open(paths['syn'], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(genre, open(paths['genre'], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(cidx, open(paths['cidx'], 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
open(os.path.join(ROOT, '.cache', 'enrich_changed_slugs.txt'), 'w', encoding='utf-8').write(','.join(changed))
if REQUEUE:
    clp = os.path.join(ROOT, 'docs', 'production-diagnostics', 'enrich-requeue-changelog.jsonl')
    with open(clp, 'a', encoding='utf-8') as f:
        for s in changed:
            f.write(json.dumps({'slug': s, 'op': 'requeue-regen', 'catch': catch.get(s), 'synopsis': syn.get(s),
                                'at': datetime.datetime.now().isoformat(timespec='seconds')}, ensure_ascii=False) + '\n')
print(f'applied (missing=0 / 変更slugは .cache/enrich_changed_slugs.txt)')
