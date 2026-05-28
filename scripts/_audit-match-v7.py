"""match v7 = v6 + author signal (= 種2 series_authors ↔ 種a staff.native)。

v6 比 強化点:
  作者突合を score に追加 (= 種2 の最強 signal)
    - 種3 key (= series_key) → 種2 series_authors → mangaka.name (+ alt_names)
    - 種a candidate → staff.edges[].node.name.native
    - 作者 native 一致     : +60 (= 決定打)
    - 両方作者あり 不一致   : -40 (= コミカライズ vs 本編 / 同名異作品 を弾く)
    - 片方欠落             : 0  (= 種2 作者カバー率 40% のため中立)

channels / year / vol は v6 と同一。
threshold: 130 / 150 / 180 で比較。
"""
import sys, gzip, json, yaml, re, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

SYL_3 = {
    'kya':'キャ','kyu':'キュ','kyo':'キョ','gya':'ギャ','gyu':'ギュ','gyo':'ギョ',
    'sha':'シャ','shu':'シュ','sho':'ショ','shi':'シ','cha':'チャ','chu':'チュ','cho':'チョ','chi':'チ',
    'ja':'ジャ','ju':'ジュ','jo':'ジョ','nya':'ニャ','nyu':'ニュ','nyo':'ニョ',
    'hya':'ヒャ','hyu':'ヒュ','hyo':'ヒョ','bya':'ビャ','byu':'ビュ','byo':'ビョ',
    'pya':'ピャ','pyu':'ピュ','pyo':'ピョ','mya':'ミャ','myu':'ミュ','myo':'ミョ',
    'rya':'リャ','ryu':'リュ','ryo':'リョ','tsu':'ツ',
}
SYL_2 = {
    'ka':'カ','ki':'キ','ku':'ク','ke':'ケ','ko':'コ','ga':'ガ','gi':'ギ','gu':'グ','ge':'ゲ','go':'ゴ',
    'sa':'サ','su':'ス','se':'セ','so':'ソ','za':'ザ','ji':'ジ','zu':'ズ','ze':'ゼ','zo':'ゾ',
    'ta':'タ','te':'テ','to':'ト','da':'ダ','de':'デ','do':'ド',
    'na':'ナ','ni':'ニ','nu':'ヌ','ne':'ネ','no':'ノ',
    'ha':'ハ','hi':'ヒ','fu':'フ','he':'ヘ','ho':'ホ','ba':'バ','bi':'ビ','bu':'ブ','be':'ベ','bo':'ボ',
    'pa':'パ','pi':'ピ','pu':'プ','pe':'ペ','po':'ポ','ma':'マ','mi':'ミ','mu':'ム','me':'メ','mo':'モ',
    'ya':'ヤ','yu':'ユ','yo':'ヨ','ra':'ラ','ri':'リ','ru':'ル','re':'レ','ro':'ロ',
    'wa':'ワ','wo':'ヲ',
}
SYL_1 = {'a':'ア','i':'イ','u':'ウ','e':'エ','o':'オ','n':'ン'}
CONSONANTS = set('kgsztcdnhfbpmyrwvj')

def hepburn_to_kata(s):
    if not s: return ''
    s = s.lower().replace('-', '')
    out = []; i = 0
    while i < len(s):
        c = s[i]
        if not c.isascii(): out.append(c); i += 1; continue
        if not c.isalpha(): i += 1; continue
        if i+1 < len(s) and c == s[i+1] and c in CONSONANTS: out.append('ッ'); i += 1; continue
        if i+3 <= len(s) and s[i:i+3] in SYL_3: out.append(SYL_3[s[i:i+3]]); i += 3; continue
        if i+2 <= len(s) and s[i:i+2] in SYL_2: out.append(SYL_2[s[i:i+2]]); i += 2; continue
        if c in SYL_1: out.append(SYL_1[c]); i += 1; continue
        i += 1
    return ''.join(out)

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

def author_norm(s):
    """作者名 norm = 空白/中黒/記号 除去。 日本人名は native 同士比較。"""
    if not s: return ''
    s = re.sub(r'[\s　・･.,，、]+', '', s)
    return s.strip().lower()

def score_match(s3_year, s3_vols, sa_year, sa_vols, sa_format, n_channels,
                s3_authors, sa_authors):
    """v7 = v6 + author signal。 returns (score, reasons[])"""
    if sa_format == 'NOVEL':
        return -200, ['format=NOVEL_reject']
    score = 100
    reasons = ['title_hit']
    # multi-channel
    if n_channels >= 4: score += 50; reasons.append('ch4+50')
    elif n_channels == 3: score += 30; reasons.append('ch3+30')
    elif n_channels == 2: score += 15; reasons.append('ch2+15')
    # author signal (= 種2 最強)
    if s3_authors and sa_authors:
        if s3_authors & sa_authors:
            score += 60; reasons.append('author_match+60')
        else:
            score -= 40; reasons.append('author_MISMATCH-40')
    # year
    if s3_year and sa_year:
        d = abs(s3_year - sa_year)
        if d == 0: score += 50; reasons.append('year_exact')
        elif d <= 1: score += 30; reasons.append(f'year_diff={d}')
        elif d <= 3: score += 10; reasons.append(f'year_diff={d}')
        elif d > 5: score -= 50; reasons.append(f'year_diff={d}!')
    # volumes
    if s3_vols and sa_vols:
        d = abs(s3_vols - sa_vols)
        if d == 0: score += 30; reasons.append(f'vol_exact={s3_vols}')
        elif d <= 2: score += 15; reasons.append(f'vol_diff={d}')
        elif d <= 5: score += 5; reasons.append(f'vol_diff={d}')
    return score, reasons

def main():
    print('loading 種2 (year/vol + authors)...', flush=True)
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
    # series_key → author norm set (name + alt_names)
    sk_authors = defaultdict(set)
    for sk, name, alt in db.execute('''
        SELECT s.series_key, m.name, m.alt_names
        FROM series s JOIN series_authors sa ON sa.series_id = s.id
        JOIN mangaka m ON m.id = sa.mangaka_id
    '''):
        an = author_norm(name)
        if an: sk_authors[sk].add(an)
        if alt:
            for a in alt.split('|'):
                aa = author_norm(a)
                if aa: sk_authors[sk].add(aa)
    db.close()
    print(f'  種2 series with author: {len(sk_authors):,}', flush=True)

    print('loading 種3...', flush=True)
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    shu3_entries = []
    for entry in data['series']:
        key = entry.get('key', '')
        title_parts = [p[5:] for p in key.split('|') if p.startswith('name:')]
        if not title_parts: continue
        title = title_parts[-1]
        kana = entry.get('title_kana') or ''
        shu3_entries.append({
            'key': key, 'title': title, 'kana': kana,
            'tn': title_norm(title), 'kn': kata_norm(kana),
            'year': sk_year.get(key), 'vols': sk_vols.get(key),
            'authors': sk_authors.get(key, set()),
        })
    print(f'  種3 entries: {len(shu3_entries):,}', flush=True)

    print('loading 種a + 4 channel + staff...', flush=True)
    idx_a = defaultdict(list); idx_b = defaultdict(list)
    idx_c = defaultdict(list); idx_d = defaultdict(list)
    entries = []
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            t = e.get('title') or {}
            authors = set()
            for ed in (e.get('staff') or {}).get('edges') or []:
                nat = (ed.get('node') or {}).get('name', {}).get('native')
                an = author_norm(nat)
                if an: authors.add(an)
            entry = {
                'native': t.get('native') or '', 'en': t.get('english') or '',
                'romaji': t.get('romaji') or '', 'syn': e.get('synonyms') or [],
                'format': e.get('format'), 'year': (e.get('startDate') or {}).get('year'),
                'vols': e.get('volumes'), 'id': e.get('id'), 'authors': authors,
            }
            ei = len(entries); entries.append(entry)
            for c in [entry['native'], entry['en']]:
                n = title_norm(c)
                if n: idx_a[n].append(ei)
            for syn in entry['syn']:
                n = title_norm(syn)
                if n: idx_a[n].append(ei)
            if entry['romaji']:
                r = entry['romaji'].split(':')[0].strip()
                r = re.sub(r'\s+-\s+.*$', '', r)
                kn = kata_norm(hepburn_to_kata(r))
                if kn and len(kn) >= 3: idx_b[kn].append(ei)
            if entry['native']:
                kn = native_kana_form(entry['native'])
                if kn and len(kn) >= 2: idx_c[kn].append(ei)
            for syn in entry['syn']:
                kn = native_kana_form(syn)
                if kn and len(kn) >= 3: idx_d[kn].append(ei)
    print(f'  種a entries: {len(entries):,}', flush=True)

    print('matching with v7 (= +author) scoring...', flush=True)
    no_match = rejected = ambiguous = 0
    by_threshold = {130: 0, 150: 0, 180: 0}
    # author signal 効果計測
    author_used = author_match = author_mismatch_reject = 0
    score_hist = defaultdict(int)
    author_flip_samples = []   # author signal で 採用先が変わった or 弾けた例
    high_authmatch_samples = []

    for s in shu3_entries:
        cand_channels = defaultdict(set)
        if s['tn']:
            for ei in idx_a.get(s['tn'], []): cand_channels[ei].add('A')
        if s['kn']:
            for ei in idx_b.get(s['kn'], []): cand_channels[ei].add('B')
            for ei in idx_c.get(s['kn'], []): cand_channels[ei].add('C')
            for ei in idx_d.get(s['kn'], []): cand_channels[ei].add('D')
        if not cand_channels:
            no_match += 1; continue
        scored = []
        for ei, chs in cand_channels.items():
            e = entries[ei]
            sc, rs = score_match(s['year'], s['vols'], e['year'], e['vols'],
                                 e['format'], len(chs), s['authors'], e['authors'])
            scored.append((sc, ei, rs, chs))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_sc, top_ei, top_rs, top_chs = scored[0]
        # author signal が top に効いたか
        if 'author_match+60' in top_rs:
            author_used += 1; author_match += 1
            if len(high_authmatch_samples) < 8:
                high_authmatch_samples.append((s, entries[top_ei], top_sc, top_rs, top_chs))
        if top_sc < 100:
            rejected += 1
            if 'author_MISMATCH-40' in top_rs and len(author_flip_samples) < 10:
                author_flip_samples.append((s, entries[top_ei], top_sc, top_rs, top_chs))
            continue
        if len(scored) >= 2 and (scored[0][0] - scored[1][0]) < 30:
            ambiguous += 1
        score_hist[top_sc] += 1
        for th in by_threshold:
            if top_sc >= th: by_threshold[th] += 1

    total = len(shu3_entries)
    print()
    print(f'=== v7 マッチ結果 ({total:,} 種3 entries) ===')
    print(f'  no match:                             {no_match:,} ({no_match*100/total:.1f}%)')
    print(f'  rejected (score < 100):               {rejected:,} ({rejected*100/total:.1f}%)')
    print(f'  accepted (score >= 100):              {total - no_match - rejected:,}')
    print(f'  ambiguous (= 2 候補で score 差 < 30): {ambiguous:,}')
    print()
    print(f'=== author signal 効果 ===')
    print(f'  作者一致 (+60) が採用 top に効いた:    {author_match:,}')
    print()
    print(f'=== threshold 別 採用件数 (v7) ===')
    print(f'  score >= 180:  {by_threshold[180]:,} ({by_threshold[180]*100/total:.1f}%)')
    print(f'  score >= 150:  {by_threshold[150]:,} ({by_threshold[150]*100/total:.1f}%)')
    print(f'  score >= 130:  {by_threshold[130]:,} ({by_threshold[130]*100/total:.1f}%)')
    print()
    print(f'=== score 分布 (bins) ===')
    bins = defaultdict(int)
    for sc, n in score_hist.items():
        bins[(sc // 10) * 10] += n
    for b in sorted(bins.keys(), reverse=True):
        bar = '█' * min(60, bins[b] // 100)
        print(f'  {b:4d}-{b+9:4d}: {bins[b]:6,}  {bar}')
    print()
    print('=== 作者一致 (+60) 採用 sample ===')
    for s, e, sc, rs, chs in high_authmatch_samples[:8]:
        print(f'  [{sc}] ch={"+".join(sorted(chs))} {s["title"]!r} → en={e["en"]!r} y={e["year"]} reason={",".join(rs)}')
    print()
    print('=== ★ author MISMATCH で reject (= 同名異作品/コミカライズ を弾いた) sample ===')
    for s, e, sc, rs, chs in author_flip_samples[:10]:
        print(f'  [{sc}] {s["title"]!r} 種3作者={sorted(s["authors"])} → 種a en={e["en"]!r} 種a作者={sorted(e["authors"])} reason={",".join(rs)}')

if __name__ == '__main__':
    main()
