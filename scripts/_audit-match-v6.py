"""match v6 = v5 + multi-channel 加点 + threshold 比較。

v5 比 強化点:
  1. multi-channel hit (= channel A/B/C/D) を score に加点
     - 2 channels hit: +15
     - 3 channels hit: +30
     - 4 channels hit: +50
  2. threshold を 130 / 150 / 180 で 比較
     - 130: 現状 (= title_hit + year_diff<=1)
     - 150: title_hit + year_exact 必須
     - 180: title_hit + year_exact + vol_exact 必須 (= 鉄壁)

channels (= v3 と同じ):
  A: 種3.title (native) norm ↔ 種a.{native, english, synonyms} norm
  B: 種3.title_kana ↔ 種a.romaji の Hepburn → katakana
  C: 種3.title_kana ↔ 種a.native の ひら→カタ
  D: 種3.title_kana ↔ 種a.synonyms の ひら→カタ
"""
import sys, gzip, json, yaml, re, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

# --- Hepburn → Katakana (= channel B) ---
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
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if not c.isascii():
            out.append(c); i += 1; continue
        if not c.isalpha():
            i += 1; continue
        if i+1 < len(s) and c == s[i+1] and c in CONSONANTS:
            out.append('ッ'); i += 1; continue
        if i+3 <= len(s) and s[i:i+3] in SYL_3:
            out.append(SYL_3[s[i:i+3]]); i += 3; continue
        if i+2 <= len(s) and s[i:i+2] in SYL_2:
            out.append(SYL_2[s[i:i+2]]); i += 2; continue
        if c in SYL_1:
            out.append(SYL_1[c]); i += 1; continue
        i += 1
    return ''.join(out)

# --- normalize ---
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

def score_match(s3_year, s3_vols, sa_year, sa_vols, sa_format, n_channels):
    """v6 = v5 + multi-channel 加点。 returns (score, reasons[])"""
    if sa_format == 'NOVEL':
        return -200, ['format=NOVEL_reject']
    score = 100
    reasons = ['title_hit']
    # multi-channel 加点 (= 新規)
    if n_channels >= 4: score += 50; reasons.append(f'ch4+50')
    elif n_channels == 3: score += 30; reasons.append(f'ch3+30')
    elif n_channels == 2: score += 15; reasons.append(f'ch2+15')
    # year
    if s3_year and sa_year:
        d = abs(s3_year - sa_year)
        if d == 0: score += 50; reasons.append(f'year_exact')
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
    # ----- 種2 から series → year + vols -----
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
        })
    print(f'  種3 entries: {len(shu3_entries):,}', flush=True)

    # ----- 種a ロード + 4 channel index -----
    print('loading 種a + 4 channel index...', flush=True)
    idx_a = defaultdict(list)  # channel A (= native+en+syn norm)
    idx_b = defaultdict(list)  # channel B (= romaji → katakana)
    idx_c = defaultdict(list)  # channel C (= native ひら→カタ)
    idx_d = defaultdict(list)  # channel D (= synonyms ひら→カタ)
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
            ei = len(entries); entries.append(entry)
            # A: native+en+syn norm
            for c in [entry['native'], entry['en']]:
                n = title_norm(c)
                if n: idx_a[n].append(ei)
            for syn in entry['syn']:
                n = title_norm(syn)
                if n: idx_a[n].append(ei)
            # B: romaji → katakana
            if entry['romaji']:
                r = entry['romaji'].split(':')[0].strip()
                r = re.sub(r'\s+-\s+.*$', '', r)
                kn = kata_norm(hepburn_to_kata(r))
                if kn and len(kn) >= 3:
                    idx_b[kn].append(ei)
            # C: native ひら→カタ
            if entry['native']:
                kn = native_kana_form(entry['native'])
                if kn and len(kn) >= 2: idx_c[kn].append(ei)
            # D: synonyms ひら→カタ
            for syn in entry['syn']:
                kn = native_kana_form(syn)
                if kn and len(kn) >= 3: idx_d[kn].append(ei)
    print(f'  種a entries: {len(entries):,}', flush=True)

    # ----- マッチ + v6 score -----
    print('matching with v6 (= multi-channel + date+volume) scoring...', flush=True)
    no_match = 0
    rejected = 0
    ambiguous = 0
    # threshold 別 集計
    by_threshold = {130: 0, 150: 0, 180: 0}
    # score 分布
    score_hist = defaultdict(int)
    # channel hit 分布 (= 採用された候補の channel hit 数)
    channel_hist_accepted = defaultdict(int)
    high_samples_180 = []
    high_samples_150 = []
    only_130_samples = []  # 130 <= score < 150 (= 1 年差等)
    rej_samples = []

    for s in shu3_entries:
        # 候補 集合 + 各候補ごとの channel hit 数
        cand_channels = defaultdict(set)  # ei → set of channels
        if s['tn']:
            for ei in idx_a.get(s['tn'], []): cand_channels[ei].add('A')
        if s['kn']:
            for ei in idx_b.get(s['kn'], []): cand_channels[ei].add('B')
            for ei in idx_c.get(s['kn'], []): cand_channels[ei].add('C')
            for ei in idx_d.get(s['kn'], []): cand_channels[ei].add('D')
        if not cand_channels:
            no_match += 1
            continue
        # 各候補 score
        scored = []
        for ei, chs in cand_channels.items():
            e = entries[ei]
            sc, rs = score_match(s['year'], s['vols'], e['year'], e['vols'], e['format'], len(chs))
            scored.append((sc, ei, rs, chs))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_sc, top_ei, top_rs, top_chs = scored[0]
        if top_sc < 100:
            rejected += 1
            if len(rej_samples) < 10:
                rej_samples.append((s, entries[top_ei], top_sc, top_rs, top_chs))
            continue
        if len(scored) >= 2 and (scored[0][0] - scored[1][0]) < 30:
            ambiguous += 1
        score_hist[top_sc] += 1
        channel_hist_accepted[len(top_chs)] += 1
        for th in by_threshold:
            if top_sc >= th: by_threshold[th] += 1
        if top_sc >= 180 and len(high_samples_180) < 10:
            high_samples_180.append((s, entries[top_ei], top_sc, top_rs, top_chs))
        elif top_sc >= 150 and top_sc < 180 and len(high_samples_150) < 10:
            high_samples_150.append((s, entries[top_ei], top_sc, top_rs, top_chs))
        elif top_sc >= 130 and top_sc < 150 and len(only_130_samples) < 10:
            only_130_samples.append((s, entries[top_ei], top_sc, top_rs, top_chs))

    total = len(shu3_entries)
    print()
    print(f'=== v6 マッチ結果 ({total:,} 種3 entries) ===')
    print(f'  no match:                             {no_match:,} ({no_match*100/total:.1f}%)')
    print(f'  rejected (score < 100):               {rejected:,} ({rejected*100/total:.1f}%)')
    print(f'  accepted (score >= 100):              {total - no_match - rejected:,}')
    print(f'  ambiguous (= 2 候補で score 差 < 30): {ambiguous:,}')
    print()
    print(f'=== threshold 別 採用件数 ===')
    print(f'  score >= 180 (= 鉄壁 = year_exact + vol_exact 必須):  {by_threshold[180]:,} ({by_threshold[180]*100/total:.1f}%)')
    print(f'  score >= 150 (= year_exact 必須):                     {by_threshold[150]:,} ({by_threshold[150]*100/total:.1f}%)')
    print(f'  score >= 130 (= 現状 = year_diff<=1 でも可):          {by_threshold[130]:,} ({by_threshold[130]*100/total:.1f}%)')
    print()
    print(f'=== 採用 (score >= 100) の channel hit 数分布 ===')
    for n_ch in sorted(channel_hist_accepted.keys(), reverse=True):
        print(f'  {n_ch} channels: {channel_hist_accepted[n_ch]:,}')
    print()
    print(f'=== score 分布 (top 20 bins) ===')
    bin_size = 10
    bins = defaultdict(int)
    for sc, n in score_hist.items():
        bins[(sc // bin_size) * bin_size] += n
    for b in sorted(bins.keys(), reverse=True)[:20]:
        bar = '█' * min(60, bins[b] // 100)
        print(f'  {b:4d}-{b+9:4d}: {bins[b]:6,}  {bar}')
    print()
    print('=== score >= 180 sample (= 鉄壁) ===')
    for s, e, sc, rs, chs in high_samples_180[:5]:
        print(f'  [{sc}] ch={"+".join(sorted(chs))} {s["title"]!r} (y={s["year"]} v={s["vols"]}) → en={e["en"]!r} y={e["year"]} v={e["vols"]} reason={",".join(rs)}')
    print()
    print('=== 150 <= score < 180 sample ===')
    for s, e, sc, rs, chs in high_samples_150[:5]:
        print(f'  [{sc}] ch={"+".join(sorted(chs))} {s["title"]!r} (y={s["year"]} v={s["vols"]}) → en={e["en"]!r} y={e["year"]} v={e["vols"]} reason={",".join(rs)}')
    print()
    print('=== 130 <= score < 150 sample (= 1 年差等で 不安あり) ===')
    for s, e, sc, rs, chs in only_130_samples[:5]:
        print(f'  [{sc}] ch={"+".join(sorted(chs))} {s["title"]!r} (y={s["year"]} v={s["vols"]}) → en={e["en"]!r} y={e["year"]} v={e["vols"]} reason={",".join(rs)}')
    print()
    print('=== reject sample (= year 大差 + multi-ch でも 救えず) ===')
    for s, e, sc, rs, chs in rej_samples[:5]:
        print(f'  [{sc}] ch={"+".join(sorted(chs))} {s["title"]!r} (y={s["year"]}) → en={e["en"]!r} y={e["year"]} reason={",".join(rs)}')

if __name__ == '__main__':
    main()
