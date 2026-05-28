"""種3 alternative_titles.en と 種a title.english の 一致/相違 比較。

対象 = 高信頼 マッチ (score >= 130) で 両方が en/english を 持つ entries。

分類:
  exact         = 文字列完全一致
  case_only     = 大小違いだけ
  punct_only    = 句読点/スペース/&-and 等 軽微差
  semantic_diff = 別表現 (= 「Bleach: Burn the Witch」 vs 「Bleach」 等)
"""
import sys, gzip, json, yaml, re, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict, Counter

# normalize 関数 (= 既存 multi-channel match と同じ)
PAREN_PATTERNS = [r'〜[^〜]*〜', r'～[^～]*～', r'\([^)]*\)', r'（[^）]*）', r'\[[^\]]*\]', r'【[^】]*】']
SEPARATORS = ['・','·','·','⋅','•','∙']
def hira_to_kata(s): return ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)
def title_norm(s):
    if not s: return ''
    for p in PAREN_PATTERNS: s = re.sub(p, '', s)
    s = re.sub(r'[:：].*$', '', s)
    for sep in SEPARATORS: s = s.replace(sep, '')
    return re.sub(r'[\s　]+', '', s).strip().lower()
def kata_norm(s):
    if not s: return ''
    s = re.split(r'[:：]', s, 1)[0]
    for p in PAREN_PATTERNS: s = re.sub(p, '', s)
    for sep in SEPARATORS: s = s.replace(sep, '')
    s = re.sub(r'[\s　ー]+', '', s)
    return s.lower()
def native_kana_form(s): return kata_norm(hira_to_kata(s)) if s else ''

def score_match(s3y, s3v, say, sav, saf):
    if saf == 'NOVEL': return -200
    sc = 100
    if s3y and say:
        d = abs(s3y - say)
        if d == 0: sc += 50
        elif d <= 1: sc += 30
        elif d <= 3: sc += 10
        elif d > 5: sc -= 50
    if s3v and sav:
        d = abs(s3v - sav)
        if d == 0: sc += 30
        elif d <= 2: sc += 15
        elif d <= 5: sc += 5
    return sc

# 英語タイトル 軽微差 normalize
def en_norm_loose(s):
    if not s: return ''
    s = s.lower()
    # &/and 同一視、 - / 句読点 削除、 多重空白 縮約
    s = s.replace('&', 'and')
    s = re.sub(r"['’‘]", '', s)  # apostrophe 削除
    s = re.sub(r'[^\w\s]', '', s)            # 句読点/記号削除
    s = re.sub(r'\s+', '', s)                # 空白除去
    return s

# ----- 種2 から year + 巻数 -----
print('loading 種2...', flush=True)
db = sqlite3.connect('.cache/db-v2.sqlite')
db.text_factory = lambda b: b.decode('utf-8', errors='replace')
sk_year, sk_vols = {}, {}
for sk, miny, n in db.execute('''
    SELECT s.series_key, MIN(SUBSTR(v.release_date, 1, 4)), COUNT(DISTINCT v.id)
    FROM series s JOIN editions e ON e.series_id = s.id JOIN volumes v ON v.edition_id = e.id
    WHERE e.type = 'standard' AND v.release_date IS NOT NULL GROUP BY s.series_key
'''):
    try: y = int(miny) if miny and miny.isdigit() else None
    except: y = None
    if y and 1900 <= y <= 2030: sk_year[sk] = y
    if n: sk_vols[sk] = n
db.close()

# ----- 種3 ロード -----
print('loading 種3...', flush=True)
with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
shu3 = []
for e in data['series']:
    key = e.get('key', '')
    tp = [p[5:] for p in key.split('|') if p.startswith('name:')]
    if not tp: continue
    title = tp[-1]
    at = e.get('alternative_titles') or {}
    en = at.get('en') if isinstance(at, dict) else None
    shu3.append({
        'key': key, 'title': title, 'en_shu3': en,
        'tn': title_norm(title), 'kn': kata_norm(e.get('title_kana') or ''),
        'year': sk_year.get(key), 'vols': sk_vols.get(key),
    })
print(f'  種3: {len(shu3):,}')

# ----- 種a ロード + index -----
print('loading 種a...', flush=True)
idx_a, idx_c, idx_d = defaultdict(list), defaultdict(list), defaultdict(list)
entries = []
with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
    for line in f:
        try: e = json.loads(line)
        except: continue
        t = e.get('title') or {}
        ent = {
            'native': t.get('native') or '',
            'en': t.get('english') or '',
            'romaji': t.get('romaji') or '',
            'syn': e.get('synonyms') or [],
            'format': e.get('format'),
            'year': (e.get('startDate') or {}).get('year'),
            'vols': e.get('volumes'),
        }
        ei = len(entries); entries.append(ent)
        for c in [ent['native'], ent['en']]:
            n = title_norm(c)
            if n: idx_a[n].append(ei)
        for syn in ent['syn']:
            n = title_norm(syn)
            if n: idx_a[n].append(ei)
        if ent['native']:
            kn = native_kana_form(ent['native'])
            if kn and len(kn) >= 2: idx_c[kn].append(ei)
        for syn in ent['syn']:
            kn = native_kana_form(syn)
            if kn and len(kn) >= 3: idx_d[kn].append(ei)

# ----- 高信頼マッチ + en 比較 -----
print('matching + 比較...', flush=True)
n_shu3_total = len(shu3)
n_shu3_has_en = sum(1 for s in shu3 if s['en_shu3'])
n_hi_match = 0
n_hi_with_shu3_en = 0
n_hi_with_shua_en = 0
n_hi_both_en = 0
n_exact = 0
n_case_only = 0
n_loose_match = 0  # 句読点/空白 違いだけ
n_diff = 0
diff_samples = []
loose_samples = []
case_samples = []

for s in shu3:
    cids = set()
    if s['tn']: cids.update(idx_a.get(s['tn'], []))
    if s['kn']:
        cids.update(idx_c.get(s['kn'], []))
        cids.update(idx_d.get(s['kn'], []))
    if not cids: continue
    best_sc, best_e = -999, None
    for ei in cids:
        e = entries[ei]
        sc = score_match(s['year'], s['vols'], e['year'], e['vols'], e['format'])
        if sc > best_sc: best_sc, best_e = sc, e
    if best_sc < 130: continue
    n_hi_match += 1
    en_s = (s['en_shu3'] or '').strip()
    en_a = (best_e['en'] or '').strip()
    if en_s: n_hi_with_shu3_en += 1
    if en_a: n_hi_with_shua_en += 1
    if not en_s or not en_a: continue
    n_hi_both_en += 1
    if en_s == en_a:
        n_exact += 1
    elif en_s.lower() == en_a.lower():
        n_case_only += 1
        if len(case_samples) < 10:
            case_samples.append((s['title'], en_s, en_a))
    elif en_norm_loose(en_s) == en_norm_loose(en_a):
        n_loose_match += 1
        if len(loose_samples) < 10:
            loose_samples.append((s['title'], en_s, en_a))
    else:
        n_diff += 1
        if len(diff_samples) < 30:
            diff_samples.append((s['title'], en_s, en_a))

# ----- 出力 -----
print()
print('=== 概況 ===')
print(f'  種3 全 entries:                   {n_shu3_total:,}')
print(f'  種3 で en 入り:                   {n_shu3_has_en:,}')
print(f'  高信頼 マッチ:                    {n_hi_match:,}')
print(f'  高信頼 + 種3 en:                  {n_hi_with_shu3_en:,}')
print(f'  高信頼 + 種a english:             {n_hi_with_shua_en:,}')
print(f'  高信頼 + 両方 en (= 比較可能):    {n_hi_both_en:,}')
print()
print('=== 比較結果 (= 種3 en vs 種a english) ===')
total = n_hi_both_en or 1
print(f'  完全一致 (= 文字列同):            {n_exact:,} ({n_exact*100/total:.1f}%)')
print(f'  大小違いだけ:                     {n_case_only:,} ({n_case_only*100/total:.1f}%)')
print(f'  軽微差 (= 句読点/&-and/空白):     {n_loose_match:,} ({n_loose_match*100/total:.1f}%)')
print(f'  ★ 実質相違 (= 別表現):            {n_diff:,} ({n_diff*100/total:.1f}%)')
print()
print('=== 大小違い sample ===')
for t, s, a in case_samples[:5]:
    print(f'  {t!r:40s} 種3={s!r}  種a={a!r}')
print()
print('=== 軽微差 sample ===')
for t, s, a in loose_samples[:10]:
    print(f'  {t!r:40s}')
    print(f'    種3={s!r}')
    print(f'    種a={a!r}')
print()
print('=== ★ 実質相違 sample (= AI fill 誤りの可能性) ===')
for t, s, a in diff_samples[:20]:
    print(f'  {t!r:40s}')
    print(f'    種3 (= AI fill):  {s!r}')
    print(f'    種a (= AniList):  {a!r}')
