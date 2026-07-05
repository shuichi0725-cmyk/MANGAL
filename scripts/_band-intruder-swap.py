# -*- coding: utf-8 -*-
# 混入スワップ生成: NDL正史 × 楽天裏取り の二段ゲートで intruder→真巻 を確定
# 適用機構 = volume-exclude(混入除去・slug単位) + 種4(真巻追加)
import csv, json, os, re, sys, sqlite3, unicodedata
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding='utf-8')
import yaml
ROOT = r'C:\Users\shuic\code\MANGAL'

def months(s):
    m = re.match(r'^(\d{4})[.\-/]?(\d{1,2})?', str(s or ''))
    return int(m.group(1)) * 12 + (int(m.group(2)) if m.group(2) else 6) if m else None

def vnum(v):
    m = re.search(r'\d+', str(v or ''))
    return int(m.group()) if m else None

def norm(t):
    t = unicodedata.normalize('NFKC', str(t or ''))
    return re.sub(r'[\s　・!！?？:：〜~\-＆&。、]', '', t).lower()

tm = json.load(open(f'{ROOT}/.cache/isbn-title-map.json', encoding='utf-8'))
iidx = json.load(open(f'{ROOT}/.cache/isbn-page-index.json', encoding='utf-8'))
def merge_fragments(recs):
    """NDL BibResource分割の断片結合: title/vol/date断片 + isbnのみ断片 が交互に出る型を縫合"""
    out = []
    for r in recs:
        if r.get('isbn') and not r.get('title') and out and not out[-1].get('isbn'):
            out[-1]['isbn'] = r['isbn']
        else:
            out.append(dict(r))
    return out

ndl = {}
for ln in open(f'{ROOT}/.cache/intruder-ndl.jsonl', encoding='utf-8'):
    d = json.loads(ln)
    ndl[d['slug']] = merge_fragments(d['records'])
# ★ページング版(全件)で上書き
if os.path.exists(f'{ROOT}/.cache/intruder-ndl2.jsonl'):
    for ln in open(f'{ROOT}/.cache/intruder-ndl2.jsonl', encoding='utf-8'):
        d = json.loads(ln)
        ndl[d['slug']] = merge_fragments(d['records'])

# 楽天cache直接候補: base題+巻 → isbn
VOLP = re.compile(r'[（(]\s*(\d{1,3})\s*[)）]\s*$|VOL\.?\s*(\d{1,3})\s*$|第(\d{1,3})巻\s*$', re.I)
by_tv = defaultdict(list)
for _ib, _t in tm.items():
    _t2 = unicodedata.normalize('NFKC', _t).strip()
    _m = VOLP.search(_t2)
    if not _m:
        continue
    _n = int(next(g for g in _m.groups() if g))
    by_tv[(norm(VOLP.sub('', _t2)), _n)].append(_ib)

intr = defaultdict(list)
for r in csv.reader(open(f'{ROOT}/docs/production-diagnostics/band-intruders.tsv', encoding='utf-8'), delimiter='\t'):
    if r and r[0] != 'slug':
        intr[r[0]].append((r[1], int(r[2]), r[3]))  # (etype, vol, intruder_isbn)

c = Counter()
swaps = []      # (slug, etype, vol, intruder_isbn, true_isbn, date)
manual = []
for slug, slots in intr.items():
    p = f'{ROOT}/data/manga.v2/{slug}.yml'
    if not os.path.exists(p):
        c['頁無'] += len(slots); continue
    d = yaml.safe_load(open(p, encoding='utf-8'))
    pt = norm(d.get('title'))
    for etype, gvol, bad in slots:
        e = next((x for x in d.get('editions', []) if x.get('type') == etype), None)
        if not e:
            c['edition無'] += 1; continue
        vols = [v for v in e['volumes'] if v.get('isbn13')]
        bands = Counter(str(v['isbn13'])[:7] for v in vols)
        maj = bands.most_common(1)[0][0]
        mj = {v['number']: months(v.get('release_date')) for v in vols
              if str(v['isbn13'])[:7] == maj and v.get('number')}
        lo = max([m for k, m in mj.items() if k < gvol and m], default=None)
        hi = min([m for k, m in mj.items() if k > gvol and m], default=None)
        # 候補プール = NDL(帯不問・日付付) ∪ 楽天直接(題base+巻一致)。帯は移籍作(EAT-MAN型)があるため必須にしない
        pool = {}
        for r in ndl.get(slug, []):
            ib = r.get('isbn', '')
            if vnum(r.get('vol')) == gvol and len(ib) == 13:
                pool.setdefault(ib, r.get('date', ''))
        for ib in by_tv.get((pt, gvol), []):
            pool.setdefault(ib, '')
        cands = []
        for ib, dt in pool.items():
            if ib == bad or ib in iidx:
                continue
            mm = months(dt)
            if mm is not None:
                if (lo is not None and mm < lo - 24) or (hi is not None and mm > hi + 24):
                    continue
            cands.append((ib, dt))
        if not cands:
            c['NDL候補なし'] += 1; manual.append((slug, etype, gvol, bad, 'NDL候補なし')); continue
        # 楽天裏取り: title-map題のbaseが頁題一致(cache無=保留)
        ok = []
        for ib, dt in cands:
            t2 = tm.get(ib)
            if t2 is None:
                continue
            base = norm(re.sub(r'[（(]\s*\d+\s*[)）]\s*$|第?\s*\d+\s*巻?\s*$', '', unicodedata.normalize('NFKC', t2)))
            if base == pt:
                ok.append((ib, dt))
        if not ok:
            c['楽天裏取り不可'] += 1; manual.append((slug, etype, gvol, bad, f'楽天裏取り不可 NDL候補={cands[:2]}')); continue
        if len(ok) > 1:
            c['複数候補'] += 1; manual.append((slug, etype, gvol, bad, f'複数候補{ok[:3]}')); continue
        ib, dt = ok[0]
        m = re.match(r'^(\d{4})[.\-/]?(\d{1,2})?', dt)
        ds = f'{m.group(1)}-{int(m.group(2)):02d}' if m and m.group(2) else (m.group(1) if m else None)
        swaps.append((slug, etype, gvol, bad, ib, ds))
        c['SWAP確定'] += 1

print('結果:', dict(c))
for s in swaps[:12]:
    print('  SWAP:', s)
json.dump(swaps, open(f'{ROOT}/.cache/intruder-swaps.json', 'w'))
with open(f'{ROOT}/docs/production-diagnostics/band-intruders-manual.tsv', 'w', encoding='utf-8') as f:
    f.write('slug\tedition\tvol\tintruder\treason\n')
    for m2 in manual:
        f.write('\t'.join(str(x) for x in m2) + '\n')

if '--apply' in sys.argv:
    con = sqlite3.connect(f'{ROOT}/.cache/db-v2.sqlite'); cur = con.cursor()
    vex = yaml.safe_load(open(f'{ROOT}/data/seeds/volume-exclude.yml', encoding='utf-8')) or {'excludes': []}
    doc = yaml.safe_load(open(f'{ROOT}/data/seeds/volumes-supplement.yml', encoding='utf-8'))
    exist = {str(v.get('isbn13')) for v in doc['volumes']}
    have_ex = {(x.get('slug'), str(x.get('isbn13'))) for x in vex['excludes']}
    touched = set()
    for slug, etype, gvol, bad, ib, ds in swaps:
        if (slug, bad) not in have_ex:
            vex['excludes'].append({'slug': slug, 'isbn13': bad,
                                    'note': f'激マン型混入(帯断絶×日付逆行)。真巻{ib}に差替 2026-07-04'})
            have_ex.add((slug, bad))
        if ib not in exist:
            d = yaml.safe_load(open(f'{ROOT}/data/manga.v2/{slug}.yml', encoding='utf-8'))
            e = next(x for x in d['editions'] if x.get('type') == etype)
            ks = set()
            for v in e['volumes'][:8]:
                if v.get('isbn13') and str(v['isbn13']) != bad:
                    for r in cur.execute('SELECT s.series_key FROM volumes v JOIN editions e2 ON v.edition_id=e2.id JOIN series s ON e2.series_id=s.id WHERE v.isbn13=?', (str(v['isbn13']),)):
                        ks.add(r[0])
            if not ks:
                print('  skip(key逆引き不可):', slug, ib); continue
            doc['volumes'].append({'series_keys': sorted(ks), 'qid': None, 'number': int(gvol), 'isbn13': ib,
                                   'release_date': ds, 'pages': None, 'publisher': None, 'edition_type': etype,
                                   'title_display': d.get('title'), 'source': 'band-intruder-swap', 'added_at': '2026-07-04',
                                   'note': f'激マン型スワップ(NDL正史+楽天題一致)。混入{bad}をexclude。 slug={slug}'})
            exist.add(ib)
        touched.add(slug)
    yaml.dump(vex, open(f'{ROOT}/data/seeds/volume-exclude.yml', 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False, width=200)
    yaml.dump(doc, open(f'{ROOT}/data/seeds/volumes-supplement.yml', 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False, width=200)
    json.dump(sorted(touched), open(f'{ROOT}/.cache/intruder-touched.json', 'w'))
    print(f'適用: exclude+種4 / 対象頁{len(touched)}')
