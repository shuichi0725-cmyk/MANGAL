#!/usr/bin/env python3
"""
A Phase3 (REPOINT適用): shared-isbn-actions.tsv の REPOINT slug を、自前の真ISBN群へ差替。
 各slugの「DB著者×題」に一致するISBNを種1/楽天から全収集→date順number振り→clean editions構築。
 ページが別作のenrichを抱えている恐れ→Ani(match)由来enrichはclearし次promoteで再付与。identity(題/著者/kana)は保持。
 dry-run(既定)=proposal TSV出力 / --apply=backup+changelog+書込み。可逆。種2不変。
"""
import sys, json, re, unicodedata, time, shutil, json as J
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
ROOT = Path(__file__).resolve().parent.parent
import yaml
APPLY = '--apply' in sys.argv
BASES = ('data/manga.v2', '.preview-data/manga')
CLEAR = ['anilist_id', 'synopsis', 'genres_anilist', 'tags', 'catch', 'popularity',
         'adult_us', 'alternative_titles', 'wikidata_qid', 'synonyms', 'anime_adapted']
PUBMAP = {}  # display名→key 簡易(無ければそのまま種2導出に任せ、publisher keyは触らない)

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
def atok(creator):
    s = re.sub(r'\[[^\]]*\]', '', str(creator or ''))
    return [naz(p) for p in re.split(r'[、,/／;；]| ∥ |∥', s) if naz(p)]
def vnum(title):
    m = re.search(r'[（(]\s*(\d{1,3})\s*[)）]', str(title))
    if m: return int(m.group(1))
    m = re.search(r'(\d{1,3})\s*$', re.sub(r'(巻|vol\.?)', '', str(title)))
    return int(m.group(1)) if m else None

# 1) REPOINT対象
repoint = []
for line in (ROOT/'data/seeds/shared-isbn-actions.tsv').open(encoding='utf-8'):
    c = line.rstrip('\n').split('\t')
    if c[0] == 'slug' or len(c) < 3: continue
    if c[2] == 'REPOINT': repoint.append(c[0])
tgt = {}
for sl in repoint:
    fp = ROOT/'data/manga.v2'/f'{sl}.yml'
    if not fp.exists(): continue
    d = yaml.safe_load(fp.read_text(encoding='utf-8'))
    aus = [naz(a.get('name')) for a in (d.get('authors') or []) if a.get('name')]
    tgt[sl] = {'d': d, 'authors': [a for a in aus if a], 'tc': naz(d.get('title')),
               'cur': set(to13(v.get('isbn13')) for e in d.get('editions', []) for v in e.get('volumes', []) if to13(v.get('isbn13')))}
print(f'REPOINT対象(yml存在) {len(tgt)}', flush=True)

# 2) 各slugの自前ISBN+metadata収集 (種1優先, 楽天補完)
found = {sl: {} for sl in tgt}  # sl -> isbn -> {title,date,pub,src}
def consider(ib, title, atoks, date, pub, src):
    if not ib: return
    nt = naz(title)
    if not nt: return
    for sl, t in tgt.items():
        if ib in t['cur']: continue
        if not (t['tc'] and len(t['tc']) >= 2 and (t['tc'] in nt or nt in t['tc'])): continue
        if not t['authors'] or not atoks: continue
        if any((da in ta or ta in da) for da in t['authors'] for ta in atoks):
            if ib not in found[sl] or src == '種1':
                found[sl][ib] = {'title': title, 'date': date, 'pub': pub, 'src': src}
g = json.load(open(ROOT/'.cache/madb/metadata101.json', encoding='utf-8'))['@graph']
for r in g:
    ib = to13(first(r.get('schema:isbn')))
    if ib: consider(ib, first(r.get('schema:name')) or '', atok(first(r.get('schema:creator')) or ''),
                     str(first(r.get('schema:datePublished')) or ''), str(first(r.get('schema:publisher')) or '').split('　∥')[0].strip(), '種1')
for line in (ROOT/'.cache/rakuten-isbn.jsonl').open(encoding='utf-8'):
    try: o = json.loads(line); ib = to13(o.get('isbn') or (o.get('item') or {}).get('isbn'))
    except: continue
    it = o.get('item') or {}
    if ib: consider(ib, it.get('title', ''), atok(it.get('author', '')), str(it.get('salesDate', '')), str(it.get('publisherName', '')), '楽天')
print('自前ISBN+metadata収集 完了', flush=True)

# 3) proposal構築
prop = {}  # sl -> list of vol dicts (sorted)
for sl, fmap in found.items():
    vols = []
    for ib, m in fmap.items():
        vols.append({'isbn13': ib, 'number': vnum(m['title']), 'release_date': m['date'][:7] if m['date'] else None,
                     'pub': m['pub'], 'title': m['title']})
    # 番号: 明示優先, 無いものはdate順で埋める
    vols.sort(key=lambda v: (v['release_date'] or '9999', v['isbn13']))
    nxt = 1; used = set(v['number'] for v in vols if v['number'])
    for v in vols:
        if not v['number']:
            while nxt in used: nxt += 1
            v['number'] = nxt; used.add(nxt); nxt += 1
    vols.sort(key=lambda v: v['number'])
    prop[sl] = vols

# proposal TSV
po = ROOT/'data/seeds/shared-isbn-repoint-proposal.tsv'
with open(po, 'w', encoding='utf-8') as f:
    f.write('slug\told_wrong_n\tnew_own_n\tnumbers\tnew_isbns\tpubs\ttitles\n')
    for sl in sorted(prop):
        v = prop[sl]; t = tgt[sl]
        f.write(f"{sl}\t{len(t['cur'])}\t{len(v)}\t{','.join(str(x['number']) for x in v)}\t"
                f"{','.join(x['isbn13'] for x in v)}\t{'/'.join(sorted(set(x['pub'] for x in v if x['pub'])))[:40]}\t"
                f"{'; '.join(x['title'][:22] for x in v[:4])}\n")
print(f'proposal: {po}')
multi = sum(1 for v in prop.values() if len(v) > 1)
print(f'  単巻 {sum(1 for v in prop.values() if len(v)==1)} / 複数巻 {multi}')

if not APPLY:
    print('\n(dry-run。 proposal確認後 --apply)'); sys.exit(0)

# 4) apply: clean stub化(identity保持, enrich clear, editions=自前vol)
bak = ROOT/'.cache'/f'sharedisbn-repoint-bak-{time.strftime("%Y%m%d-%H%M%S")}'; bak.mkdir(parents=True, exist_ok=True)
lf = (ROOT/'data/seeds/unmerge-changelog.jsonl').open('a', encoding='utf-8'); st = time.strftime('%Y-%m-%dT%H:%M:%S')
n = 0
for sl, vols in prop.items():
    if not vols: continue
    d = tgt[sl]['d']
    for k in CLEAR: d.pop(k, None)
    pubs = sorted(set(v['pub'] for v in vols if v['pub']))
    d['editions'] = [{'type': 'standard', 'label': '通常版', 'publisher': (pubs[0] if pubs else None),
                      'volumes': [{'number': v['number'], 'asin': None, 'isbn13': v['isbn13'], 'cover_url': None,
                                   'release_date': v['release_date']} for v in vols]}]
    for base in BASES:
        fp = ROOT/base/f'{sl}.yml'
        if base == 'data/manga.v2' or fp.exists():
            if fp.exists(): shutil.copy2(fp, bak/(base.replace('/', '_')+'__'+sl+'.yml'))
            fp.write_text(yaml.dump(d, allow_unicode=True, sort_keys=False), encoding='utf-8')
    lf.write(J.dumps({'sharedisbn_repoint': sl, 'isbns': [v['isbn13'] for v in vols], 'at': st}, ensure_ascii=False)+'\n')
    n += 1
lf.close()
print(f'\n適用 {n}件。 backup={bak}')
