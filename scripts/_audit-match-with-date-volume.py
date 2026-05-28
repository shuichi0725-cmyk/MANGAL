"""種3 ↔ 種a マッチを 発売年 + 巻数 で 確度向上。

signals:
  - title match (= 既存 multi-channel)
  - year_started: 種2 series.year_started vs 種a startDate.year
  - volume_count: 種2 (= COUNT volumes per series) vs 種a volumes (= null 多い)
  - format: 種a が NOVEL なら reject (= 漫画限定)

score:
  title hit            : +100 base (= 必須)
  year diff = 0        : +50
  year diff <= 1       : +30
  year diff <= 3       : +10
  year diff > 5        : -50
  year unknown (片方)  : 0
  volume diff = 0      : +30 (= 完全一致は強い)
  volume diff <= 2     : +15
  volume diff > 10     : -20
  volume unknown 片方  : 0
  format NOVEL         : -200 (= 即除外)

threshold: score >= 100 でマッチ採用 (= title hit のみでも採用、 ただし year/volume 矛盾はその時点で reject)

ambiguous (= 種a 同名複数) 時:
  全候補 score 計算 → 最高 score を採用、 ただし 2 位との差が 30 未満 なら 「曖昧」 とフラグ
"""
import sys, gzip, json, yaml, re, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

# normalize 関数 (= 既存と同じ)
PAREN_PATTERNS = [r'〜[^〜]*〜', r'～[^～]*～', r'\([^)]*\)', r'（[^）]*）', r'\[[^\]]*\]', r'【[^】]*】']
SEPARATORS = ['・','·','·','⋅','•','∙']

def hira_to_kata(s):
    return ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)

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

def native_kana_form(s):
    return kata_norm(hira_to_kata(s)) if s else ''

def score_match(s3_year, s3_vols, sa_year, sa_vols, sa_format):
    """発売年 + 巻数 で マッチ確度 score"""
    if sa_format == 'NOVEL':
        return -200, 'format=NOVEL reject'
    score = 100
    reasons = ['title_hit']
    # year
    if s3_year and sa_year:
        d = abs(s3_year - sa_year)
        if d == 0: score += 50; reasons.append(f'year_exact')
        elif d <= 1: score += 30; reasons.append(f'year_diff={d}')
        elif d <= 3: score += 10; reasons.append(f'year_diff={d}')
        elif d > 5: score -= 50; reasons.append(f'year_diff={d}!')
    # volumes - 種3 (= standard 限定) と 種a (= 全 edition 合算?) で差出やすい
    # 緩めに: 一致は加点、 大きな差でも reject はしない (= edition 種類で異なる)
    if s3_vols and sa_vols:
        d = abs(s3_vols - sa_vols)
        if d == 0: score += 30; reasons.append(f'vol_exact={s3_vols}')
        elif d <= 2: score += 15; reasons.append(f'vol_diff={d}')
        elif d <= 5: score += 5; reasons.append(f'vol_diff={d}')
        # else: 加減点なし
    return score, ','.join(reasons)

def main():
    # ----- 種2 から series → year_started (= MIN release_date) + 巻数 -----
    print('loading 種2 series + volume counts from release_date...', flush=True)
    db = sqlite3.connect('.cache/db-v2.sqlite')
    db.text_factory = lambda b: b.decode('utf-8', errors='replace')
    # release_date は YYYY-MM-DD or YYYY-MM or YYYY → 先頭 4 桁が year
    sk_year = {}
    sk_vols = {}
    rows = db.execute('''
        SELECT s.series_key,
               MIN(SUBSTR(v.release_date, 1, 4)) as min_year,
               COUNT(DISTINCT v.id) as n_vols
        FROM series s
        JOIN editions e ON e.series_id = s.id
        JOIN volumes v ON v.edition_id = e.id
        WHERE e.type = 'standard'
          AND v.release_date IS NOT NULL
        GROUP BY s.series_key
    ''').fetchall()
    for sk, miny, n in rows:
        try:
            y = int(miny) if miny and miny.isdigit() else None
        except: y = None
        if y and 1900 <= y <= 2030: sk_year[sk] = y
        if n: sk_vols[sk] = n
    db.close()
    print(f'  種2 series: {len(sk_year):,}, with volume counts: {len(sk_vols):,}', flush=True)

    # ----- 種3 ロード + 種2 join -----
    print('loading 種3 + join...', flush=True)
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    shu3_entries = []
    join_hit = 0
    for entry in data['series']:
        key = entry.get('key', '')
        parts = key.split('|')
        title_parts = [p[5:] for p in parts if p.startswith('name:')]
        if not title_parts: continue
        title = title_parts[-1]
        kana = entry.get('title_kana') or ''
        # 種2 から year + vol
        year = sk_year.get(key)
        vols = sk_vols.get(key)
        if year or vols: join_hit += 1
        shu3_entries.append({
            'key': key, 'title': title, 'kana': kana,
            'tn': title_norm(title), 'kn': kata_norm(kana),
            'year': year, 'vols': vols,
        })
    print(f'  種3 entries: {len(shu3_entries):,}, 種2 join hit: {join_hit:,}', flush=True)

    # ----- 種a ロード + entry index -----
    print('loading 種a...', flush=True)
    idx_a = defaultdict(list)  # norm → [entry_idx]
    idx_c = defaultdict(list)  # kana norm (native ひら→カタ) → [entry_idx]
    idx_d = defaultdict(list)  # kana norm (synonyms ひら→カタ) → [entry_idx]
    entries = []
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            t = e.get('title') or {}
            entry = {
                'native': t.get('native') or '',
                'en': t.get('english') or '',
                'romaji': t.get('romaji') or '',
                'syn': e.get('synonyms') or [],
                'format': e.get('format'),
                'year': (e.get('startDate') or {}).get('year'),
                'vols': e.get('volumes'),
                'isAdult': e.get('isAdult'),
                'id': e.get('id'),
            }
            ei = len(entries)
            entries.append(entry)
            for c in [entry['native'], entry['en']]:
                n = title_norm(c)
                if n: idx_a[n].append(ei)
            for syn in entry['syn']:
                n = title_norm(syn)
                if n: idx_a[n].append(ei)
            if entry['native']:
                kn = native_kana_form(entry['native'])
                if kn and len(kn) >= 2: idx_c[kn].append(ei)
            for syn in entry['syn']:
                kn = native_kana_form(syn)
                if kn and len(kn) >= 3: idx_d[kn].append(ei)

    print(f'  種a entries: {len(entries):,}', flush=True)

    # ----- マッチ + score -----
    print('matching with date+volume scoring...', flush=True)
    accepted_high = 0  # score >= 130 (= year/vol で 確証)
    accepted_low = 0   # score 100-129 (= title のみ、 year/vol 不明)
    rejected = 0       # score < 100
    ambiguous = 0      # 2+ 候補 score 差 < 30
    no_match = 0
    high_samples = []
    low_samples = []
    rej_samples = []

    for s in shu3_entries:
        # 候補 集合
        cand_ids = set()
        if s['tn']: cand_ids.update(idx_a.get(s['tn'], []))
        if s['kn']:
            cand_ids.update(idx_c.get(s['kn'], []))
            cand_ids.update(idx_d.get(s['kn'], []))
        if not cand_ids:
            no_match += 1
            continue
        # 各候補 score
        scored = []
        for ei in cand_ids:
            e = entries[ei]
            sc, rs = score_match(s['year'], s['vols'], e['year'], e['vols'], e['format'])
            scored.append((sc, ei, rs))
        scored.sort(reverse=True)
        top_sc, top_ei, top_rs = scored[0]
        if top_sc < 100:
            rejected += 1
            if len(rej_samples) < 10:
                rej_samples.append((s, entries[top_ei], top_sc, top_rs))
            continue
        # ambiguous check (= 2 位との差 < 30)
        if len(scored) >= 2 and (scored[0][0] - scored[1][0]) < 30:
            ambiguous += 1
        if top_sc >= 130:
            accepted_high += 1
            if len(high_samples) < 10:
                high_samples.append((s, entries[top_ei], top_sc, top_rs))
        else:
            accepted_low += 1
            if len(low_samples) < 10:
                low_samples.append((s, entries[top_ei], top_sc, top_rs))

    total = len(shu3_entries)
    print()
    print(f'=== マッチ結果 ({total:,} 種3 entries) ===')
    print(f'  高信頼 (score >= 130, year/vol 確証): {accepted_high:,} ({accepted_high*100/total:.1f}%)')
    print(f'  低信頼 (score 100-129, title のみ):   {accepted_low:,} ({accepted_low*100/total:.1f}%)')
    print(f'  rejected (year/vol 矛盾):             {rejected:,} ({rejected*100/total:.1f}%)')
    print(f'  no match:                             {no_match:,} ({no_match*100/total:.1f}%)')
    print(f'  ambiguous (= 2 候補で score 差 < 30): {ambiguous:,}')
    print()
    print('=== 高信頼 sample ===')
    for s, e, sc, rs in high_samples[:5]:
        print(f'  [{sc}] {s["title"]!r} (y={s["year"]} v={s["vols"]}) → en={e["en"]!r} y={e["year"]} v={e["vols"]} reason={rs}')
    print()
    print('=== 低信頼 sample (= title だけで採用、 year/vol どちらか欠落) ===')
    for s, e, sc, rs in low_samples[:5]:
        print(f'  [{sc}] {s["title"]!r} (y={s["year"]} v={s["vols"]}) → en={e["en"]!r} y={e["year"]} v={e["vols"]} reason={rs}')
    print()
    print('=== reject sample (= 発売年が大きく違う = 別作品) ===')
    for s, e, sc, rs in rej_samples[:10]:
        print(f'  [{sc}] {s["title"]!r} (y={s["year"]}) → en={e["en"]!r} y={e["year"]} reason={rs}')

if __name__ == '__main__':
    main()
