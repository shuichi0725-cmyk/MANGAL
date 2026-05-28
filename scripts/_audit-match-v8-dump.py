"""match v8 = v7 + 作者名 姓名順 吸収 (= 文字 multiset 突合)。

v7 比 強化点:
  作者突合で 姓名順 逆転 を吸収:
    - v7: norm (= 空白除去) 完全一致 のみ → 「黒乃奈々絵」 ≠ 「奈々絵黒乃」 で誤 reject
    - v8: norm 完全一致 OR ソート文字列 (= 文字 multiset) 一致
      ソート一致は 誤検出 防止のため len >= 4 字に限定
  → AniList native 名が 「名+姓」 逆順 のケースを 同一作者と判定

author signal score は v7 と同じ:
    - 作者 一致 : +60、 両方あり 不一致 : -40、 片方欠落 : 0
channels / year / vol は v6 と同一。 threshold: 130 / 150 / 180 で比較。
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

def author_sortkey(norm):
    """norm 済 作者名を 文字 multiset (= ソート文字列) に。 姓名順 逆転 吸収用。
    誤検出防止で len >= 4 字のみ有効、 短い名は '' (= 無効)。"""
    if not norm or len(norm) < 4: return ''
    return ''.join(sorted(norm))

def author_match(s3_norm, s3_sort, sa_norm, sa_sort):
    """作者一致判定: norm 完全一致 OR sortkey 一致 (= 姓名順逆転)。"""
    if s3_norm & sa_norm: return True
    if s3_sort & sa_sort: return True
    return False

def score_match(s3_year, s3_vols, sa_year, sa_vols, sa_format, n_channels,
                s3_authors, sa_authors, s3_asort, sa_asort):
    """v8 = v7 + 姓名順吸収 author。 returns (score, reasons[])"""
    if sa_format == 'NOVEL':
        return -200, ['format=NOVEL_reject']
    score = 100
    reasons = ['title_hit']
    # multi-channel
    if n_channels >= 4: score += 50; reasons.append('ch4+50')
    elif n_channels == 3: score += 30; reasons.append('ch3+30')
    elif n_channels == 2: score += 15; reasons.append('ch2+15')
    # author signal (= 種2 最強、 姓名順 逆転 吸収)
    if s3_authors and sa_authors:
        if author_match(s3_authors, s3_asort, sa_authors, sa_asort):
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
    # series_key → author norm set + sortkey set (name + alt_names)
    sk_authors = defaultdict(set)
    sk_asort = defaultdict(set)
    for sk, name, alt in db.execute('''
        SELECT s.series_key, m.name, m.alt_names
        FROM series s JOIN series_authors sa ON sa.series_id = s.id
        JOIN mangaka m ON m.id = sa.mangaka_id
    '''):
        for nm in [name] + (alt.split('|') if alt else []):
            an = author_norm(nm)
            if an:
                sk_authors[sk].add(an)
                ak = author_sortkey(an)
                if ak: sk_asort[sk].add(ak)
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
        at = entry.get('alternative_titles') or {}
        en3 = at.get('en') if isinstance(at, dict) else None
        shu3_entries.append({
            'key': key, 'title': title, 'kana': kana, 'en3': en3 or '',
            'tn': title_norm(title), 'kn': kata_norm(kana),
            'year': sk_year.get(key), 'vols': sk_vols.get(key),
            'authors': sk_authors.get(key, set()),
            'asort': sk_asort.get(key, set()),
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
            authors = set(); asort = set()
            for ed in (e.get('staff') or {}).get('edges') or []:
                nat = (ed.get('node') or {}).get('name', {}).get('native')
                an = author_norm(nat)
                if an:
                    authors.add(an)
                    ak = author_sortkey(an)
                    if ak: asort.add(ak)
            entry = {
                'native': t.get('native') or '', 'en': t.get('english') or '',
                'romaji': t.get('romaji') or '', 'syn': e.get('synonyms') or [],
                'format': e.get('format'), 'year': (e.get('startDate') or {}).get('year'),
                'vols': e.get('volumes'), 'id': e.get('id'),
                'authors': authors, 'asort': asort,
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

    print('matching with v8 + 全件 TSV dump...', flush=True)
    total = len(shu3_entries)
    OUT_TSV = '.cache/match-v8-all.tsv'
    # verdict 区分: NO_MATCH / REJECT / S100 / S130 / S150 / S180
    def verdict_of(sc):
        if sc >= 180: return 'S180'
        if sc >= 150: return 'S150'
        if sc >= 130: return 'S130'
        if sc >= 100: return 'S100'
        return 'REJECT'

    cnt = defaultdict(int)            # verdict → count
    score_hist = defaultdict(int)
    ambiguous = 0
    author_match = author_mismatch = 0
    # en 転記 機会 (= 種a に en あり、 種3 に en なし、 score 帯別)
    en_fill_chance = defaultdict(int)   # verdict → count (種a en あり & 種3 en 空)
    en_both = defaultdict(int)          # verdict → 両方 en あり (= 差分検証可能)
    cols = ['verdict','score','channels','reason','ambiguous',
            's3_key','s3_title','s3_kana','s3_year','s3_vols','s3_authors','s3_en',
            'a_id','a_native','a_en','a_romaji','a_year','a_vols','a_authors']
    f_out = open(OUT_TSV, 'w', encoding='utf-8', newline='')
    f_out.write('\t'.join(cols) + '\n')

    def clean(x):
        return str(x).replace('\t',' ').replace('\n',' ').replace('\r',' ') if x is not None else ''

    for s in shu3_entries:
        cand_channels = defaultdict(set)
        if s['tn']:
            for ei in idx_a.get(s['tn'], []): cand_channels[ei].add('A')
        if s['kn']:
            for ei in idx_b.get(s['kn'], []): cand_channels[ei].add('B')
            for ei in idx_c.get(s['kn'], []): cand_channels[ei].add('C')
            for ei in idx_d.get(s['kn'], []): cand_channels[ei].add('D')
        if not cand_channels:
            cnt['NO_MATCH'] += 1
            row = ['NO_MATCH','','','','',
                   s['key'],s['title'],s['kana'],s['year'] or '',s['vols'] or '',
                   '|'.join(sorted(s['authors'])),s['en3'],
                   '','','','','','','']
            f_out.write('\t'.join(clean(x) for x in row) + '\n')
            continue
        scored = []
        for ei, chs in cand_channels.items():
            e = entries[ei]
            sc, rs = score_match(s['year'], s['vols'], e['year'], e['vols'],
                                 e['format'], len(chs), s['authors'], e['authors'],
                                 s['asort'], e['asort'])
            scored.append((sc, ei, rs, chs))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_sc, top_ei, top_rs, top_chs = scored[0]
        e = entries[top_ei]
        amb = 1 if (len(scored) >= 2 and (scored[0][0]-scored[1][0]) < 30) else 0
        v = verdict_of(top_sc)
        cnt[v] += 1
        if 'author_match+60' in top_rs: author_match += 1
        if 'author_MISMATCH-40' in top_rs: author_mismatch += 1
        if v != 'REJECT':
            score_hist[top_sc] += 1
            ambiguous += amb
            if e['en'] and not s['en3']: en_fill_chance[v] += 1
            if e['en'] and s['en3']: en_both[v] += 1
        row = [v, top_sc, '+'.join(sorted(top_chs)), ','.join(top_rs), amb,
               s['key'], s['title'], s['kana'], s['year'] or '', s['vols'] or '',
               '|'.join(sorted(s['authors'])), s['en3'],
               e['id'], e['native'], e['en'], e['romaji'], e['year'] or '',
               e['vols'] or '', '|'.join(sorted(e['authors']))]
        f_out.write('\t'.join(clean(x) for x in row) + '\n')
    f_out.close()

    # ----- summary -----
    accepted = cnt['S180'] + cnt['S150'] + cnt['S130'] + cnt['S100']
    print()
    print(f'=== v8 全件マッチ状況 ({total:,} 種3 entries) ===')
    print(f'  全 TSV 出力: {OUT_TSV}')
    print()
    print(f'  NO_MATCH (種a に候補なし)      : {cnt["NO_MATCH"]:,} ({cnt["NO_MATCH"]*100/total:.1f}%)')
    print(f'  REJECT   (候補ありだが score<100): {cnt["REJECT"]:,} ({cnt["REJECT"]*100/total:.1f}%)')
    print(f'  ACCEPT   (score>=100)          : {accepted:,} ({accepted*100/total:.1f}%)')
    print()
    print(f'  --- ACCEPT 内訳 (verdict 別) ---')
    print(f'    S180 (鉄壁 >=180)            : {cnt["S180"]:,}')
    print(f'    S150 (150-179)              : {cnt["S150"]:,}')
    print(f'    S130 (130-149)              : {cnt["S130"]:,}')
    print(f'    S100 (100-129 = title薄い)  : {cnt["S100"]:,}')
    print(f'    うち ambiguous (2位と僅差)  : {ambiguous:,}')
    print()
    print(f'=== author signal ===')
    print(f'  採用で 作者一致(+60)         : {author_match:,}')
    print(f'  作者不一致(-40)で減点        : {author_mismatch:,}')
    print()
    print(f'=== en 補完 機会 (= 種a に en あり) ===')
    print(f'  verdict | 種3 en 空→種a で埋まる | 両方 en あり(差分検証可)')
    for v in ['S180','S150','S130','S100']:
        print(f'    {v}  |  {en_fill_chance[v]:6,}              |  {en_both[v]:6,}')
    tot_fill = sum(en_fill_chance[v] for v in ['S180','S150','S130','S100'])
    tot_fill_safe = en_fill_chance['S180'] + en_fill_chance['S150']
    print(f'  → en 補完 候補 合計        : {tot_fill:,}')
    print(f'  → うち 安全帯(S150+S180)のみ: {tot_fill_safe:,}')
    print()
    print(f'=== score 分布 (bins) ===')
    bins = defaultdict(int)
    for sc, n in score_hist.items():
        bins[(sc // 10) * 10] += n
    for b in sorted(bins.keys(), reverse=True):
        bar = '█' * min(60, bins[b] // 100)
        print(f'  {b:4d}-{b+9:4d}: {bins[b]:6,}  {bar}')

if __name__ == '__main__':
    main()
