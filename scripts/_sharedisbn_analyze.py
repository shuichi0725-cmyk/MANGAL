#!/usr/bin/env python3
"""
A: 同一ISBN複数作品(T3核心) 全件分析 (= Phase1, READ-ONLY)。
 resolve-master.tsv の共有ISBN(isbn_used_by_works>=2)について、種1/楽天で各ISBNの「真の題・著者」を引き、
 各slugが各ISBNの正当な持ち主か(著者一致)を判定。slug単位で分類して報告TSVを出す。書込み一切なし。
出力: .cache/_shared_analysis.json (集計) + data/seeds/shared-isbn-classified.tsv (slug別判定)
"""
import sys, json, re, unicodedata
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml

def to13(s):
    s = str(s or '').replace('-', '').strip()
    return s if len(s) == 13 and s.isdigit() else ''
def first(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str): return x
            if isinstance(x, dict) and x.get('@value'): return x['@value']
    return v
def hk(s): return re.sub(r'[ぁ-ん]', lambda m: chr(ord(m.group())+0x60), s)
def naz(s): return hk(re.sub(r'[\s　・。.,:：（）()【】「」!！?？～~ー\-/／∥0-9０-９]', '', unicodedata.normalize('NFKC', str(s or '')))).lower()
def author_tokens(creator):
    # 種1 creator: "[著]山田太郎、[作画]鈴木∥スズキ" 等 → naz tokens
    s = re.sub(r'\[[^\]]*\]', '', str(creator or ''))
    parts = re.split(r'[、,/／;；]| ∥ |∥', s)
    return [naz(p) for p in parts if naz(p)]

print('種1+楽天 共有ISBN分のみロード...', flush=True)
# 1) 共有ISBN集合 + slug/title
shared = {}  # isbn -> list of {slug,title}
rows = 0
with open(ROOT/'data/seeds/resolve-master.tsv', encoding='utf-8') as f:
    next(f)
    for line in f:
        c = line.rstrip('\n').split('\t')
        if len(c) < 10: continue
        try: used = int(c[9])
        except: continue
        if used >= 2 and c[4]:
            ib = to13(c[4])
            if ib: shared.setdefault(ib, []).append({'slug': c[0], 'title': c[1], 'edition': c[2], 'vol': c[3]})
        rows += 1
SH = set(shared)
print(f'  共有ISBN {len(SH)} / 参照行 {rows}', flush=True)

# 2) ISBN -> 真(title, author tokens) from 種1優先, 楽天補完
TRUE = {}  # isbn -> {'title':..., 'authors':[naz...], 'src':...}
g = json.load(open(ROOT/'.cache/madb/metadata101.json', encoding='utf-8'))['@graph']
for r in g:
    ib = to13(first(r.get('schema:isbn')))
    if ib in SH:
        TRUE[ib] = {'title': first(r.get('schema:name')) or '', 'authors': author_tokens(first(r.get('schema:creator')) or ''), 'src': '種1'}
for line in (ROOT/'.cache/rakuten-isbn.jsonl').open(encoding='utf-8'):
    try: o = json.loads(line); ib = to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
    except: continue
    if ib in SH and ib not in TRUE:
        it = o.get('item') or {}
        TRUE[ib] = {'title': it.get('title', ''), 'authors': author_tokens(it.get('author', '')), 'src': '楽天'}
print(f'  真owner判明ISBN {len(TRUE)}/{len(SH)}', flush=True)

# 3) slug -> DB authors (yml読み)
slugs = sorted({s['slug'] for v in shared.values() for s in v})
SAU = {}  # slug -> [naz author...]
for sl in slugs:
    fp = ROOT/'data/manga.v2'/f'{sl}.yml'
    if not fp.exists(): SAU[sl] = None; continue
    try:
        d = yaml.safe_load(fp.read_text(encoding='utf-8'))
        au = [naz(a.get('name')) for a in (d.get('authors') or []) if a.get('name')]
        au += [naz(a.get('name')) for a in (d.get('original_authors') or []) if a.get('name')]
        SAU[sl] = [a for a in au if a]
    except: SAU[sl] = None
print(f'  slug著者ロード {len(slugs)}', flush=True)

def author_match(db_aus, true_aus):
    if not db_aus or not true_aus: return None  # 判定不可
    for da in db_aus:
        for ta in true_aus:
            if da and ta and (da in ta or ta in da): return True
    return False

# 4) 判定: 各(isbn,slug)について rightful?
per_slug = {}  # slug -> {'ok':n,'wrong':n,'unknown':n,'isbns':[(isbn,verdict,true_title,true_auth)]}
for ib, holders in shared.items():
    t = TRUE.get(ib)
    for h in holders:
        sl = h['slug']
        ps = per_slug.setdefault(sl, {'ok': 0, 'wrong': 0, 'unknown': 0, 'isbns': []})
        if not t:
            v = 'no_truth'; ps['unknown'] += 1
        else:
            m = author_match(SAU.get(sl), t['authors'])
            if m is True: v = 'ok'; ps['ok'] += 1
            elif m is False: v = 'WRONG'; ps['wrong'] += 1
            else: v = 'unknown'; ps['unknown'] += 1
        ps['isbns'].append({'isbn': ib, 'verdict': v, 'true_title': (t['title'][:30] if t else ''), 'true_auth': ('/'.join(t['authors'])[:24] if t else ''), 'nshare': len(holders)})

# 5) slug分類
def classify(ps):
    ok, wr, un = ps['ok'], ps['wrong'], ps['unknown']
    tot = ok + wr + un
    if wr == 0 and ok > 0: return 'CLEAN_owner'        # 全部正当=被害者側(他slugが誤claim)
    if wr > 0 and ok == 0 and un == 0: return 'ALL_WRONG'   # 全ISBN誤=要re-point/strip/alias
    if wr > 0 and ok > 0: return 'MIXED_deinterleave'  # 一部正/一部誤=de-interleave型
    if wr > 0: return 'WRONG_plus_unknown'
    return 'UNKNOWN_only'

cls = {}
for sl, ps in per_slug.items():
    cls[sl] = classify(ps)
from collections import Counter
summary = Counter(cls.values())
print('\n=== slug分類 ===')
for k, n in summary.most_common(): print(f'  {k}: {n}')

# TSV出力
out = ROOT/'data/seeds/shared-isbn-classified.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('slug\tclass\tok\twrong\tunknown\tdb_authors\tsample_isbn\tsample_verdict\ttrue_title\ttrue_author\tmax_nshare\n')
    for sl in sorted(per_slug, key=lambda s: (cls[s], -per_slug[s]['wrong'])):
        ps = per_slug[sl]
        # 代表の誤ISBN(なければ先頭)
        bad = next((x for x in ps['isbns'] if x['verdict'] == 'WRONG'), ps['isbns'][0])
        dba = '/'.join(SAU.get(sl) or []) if SAU.get(sl) is not None else '(no_yml)'
        mx = max(x['nshare'] for x in ps['isbns'])
        f.write(f"{sl}\t{cls[sl]}\t{ps['ok']}\t{ps['wrong']}\t{ps['unknown']}\t{dba}\t{bad['isbn']}\t{bad['verdict']}\t{bad['true_title']}\t{bad['true_auth']}\t{mx}\n")

json.dump({'summary': dict(summary), 'shared_isbn': len(SH), 'truth_known': len(TRUE),
           'slugs': len(slugs)}, open(ROOT/'.cache/_shared_analysis.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'\n出力: {out}')
print('  .cache/_shared_analysis.json')
