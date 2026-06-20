#!/usr/bin/env python3
"""
NDL著者ヨミ対応の再分類 (READ-ONLY): _unresolved.json(92slug+現ISBN+slug著者) を
_ndl_isbn_map.json(NDLのISBN別 著者名+ヨミ) で再判定。slug著者を name正規化(異体字) と ヨミ の
両方で照合 → かな漢字/異体字の誤判定を根治。
出力: data/seeds/shared-isbn-ndl-class.tsv + .cache/_ndl_strip_map.json(SAFE_STRIP用)
"""
import sys, json, re, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
VAR = str.maketrans('髙﨑德濵齋齊澤眞驒嶋', '高崎徳浜斎斉沢真騨島')
def nm(s): return re.sub(r'[\s　・,，、。\-/／･\.]', '', unicodedata.normalize('NFKC', str(s or '')).translate(VAR))
def kata(s):
    s = unicodedata.normalize('NFKC', str(s or ''))
    s = re.sub(r'[ぁ-ん]', lambda m: chr(ord(m.group())+0x60), s)
    return re.sub(r'[\s　・,，、。\-/／･\.ー]', '', s)
def atok(name):  # NDL/種1 creator → tokens (役割除去)
    s = re.sub(r'\[[^\]]*\]', '', str(name or ''))
    s = re.sub(r'\b\d{4}-\d{0,4}\b', '', s)  # 生没年除去
    return [t for t in re.split(r'[、,/／;；]| ', s) if t.strip()]

U = json.load(open(ROOT/'.cache/_unresolved.json', encoding='utf-8'))
M = json.load(open(ROOT/'.cache/_ndl_isbn_map.json', encoding='utf-8'))

def author_match(slug_au, ndl_authors):
    # slug_au=[(name,kana)], ndl_authors=[(name,yomi)]
    sn = [nm(a[0]) for a in slug_au if a[0]]
    sk = [kata(a[1]) for a in slug_au if a[1]] + [kata(a[0]) for a in slug_au if a[0]]
    for name, yomi in ndl_authors:
        for tok in atok(name):
            tn = nm(tok)
            if any(s and (s in tn or tn in s) for s in sn): return True
        ty = kata(yomi)
        if ty and any(s and (s in ty or ty in s) for s in sk): return True
    return False

rows = []
strip_map = {}
for sl, d in U.items():
    own = wrong = unk = 0
    wrong_isbns = []
    for ib in d['isbns']:
        rec = M.get(ib)
        if not rec or rec.get('err') or not rec.get('authors'):
            unk += 1; continue
        if author_match(d['authors'], rec['authors']):
            own += 1
        else:
            wrong += 1
            wrong_isbns.append((ib, (rec.get('title') or '')[:18], '/'.join(a[0] for a in rec['authors'])[:16]))
    if wrong == 0:
        v = 'CLEAN' if own > 0 else 'ALLUNK'
    elif d['n_ed'] > 1:
        v = 'STRIP_multied'
    elif own >= 1:
        v = 'STRIP'
    else:
        v = 'REPOINT_full'
    if v == 'STRIP':
        strip_map[sl] = sorted(set(ib for ib, _, _ in wrong_isbns))
    rows.append({'slug': sl, 'v': v, 'own': own, 'wrong': wrong, 'unk': unk, 'n_ed': d['n_ed'],
                 'au': '/'.join(a[0] for a in d['authors'] if a[0]), 'wrong_isbns': wrong_isbns})

from collections import Counter
print('=== NDL-yomi 再分類 ===')
for k, n in Counter(r['v'] for r in rows).most_common(): print(f'  {k}: {n}')
out = ROOT/'data/seeds/shared-isbn-ndl-class.tsv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('slug\tverdict\town\twrong\tunk\tn_ed\tauthors\twrong_isbns\n')
    for r in sorted(rows, key=lambda x: (x['v'], -x['wrong'])):
        wi = '; '.join(f'{ib}({t}/{a})' for ib, t, a in r['wrong_isbns'][:3])
        f.write(f"{r['slug']}\t{r['v']}\t{r['own']}\t{r['wrong']}\t{r['unk']}\t{r['n_ed']}\t{r['au']}\t{wi}\n")
json.dump(strip_map, open(ROOT/'.cache/_ndl_strip_map.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'出力: {out} / STRIP {len(strip_map)}件')
