"""match v9 = v8 + 競合解決(種a視点 1対1) + 加点signal + 短編集除外。

v8 比 強化点:
  1. 種a 視点の 競合解決 (= greedy 1対1 割り当て):
     全(種3, 種a, score>=100)ペアを score 降順に並べ、上から
     「種3 も 種a も 未割当なら 確定」。 同一作品を 複数種3 が取り合う時、
     最高 score の 種3 が 種a を 勝ち取り、 敗者は 次善候補へ自動 fallback。
  2. 加点 signal (= 不一致では 減点しない、 正しいものだけ格上げ):
     - key著者 一致 +40 (= 種3 key の name:著者、 MADB欄 低品質ゆえ 加点のみ)
     - en 軽微一致 +40 (= 両方 en あり & 正規化一致)
  3. 短編集除外: 種a native が 短編集/全集 かつ 種3 が 個別作品 なら
     候補から除外 (= 個別短編を 短編集に 誤集約させない)。

v8 までの signal (= title 4ch / 種2 author / 姓名順 / year / vol) は継承。
threshold: 130 / 150 / 180。 全 TSV: .cache/match-v9-all.tsv
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

COLL_PATTERNS = ['傑作選','傑作集','アンソロジー','自選集','短編集','作品集','全集',
                 '大全集','選集','名作集','コレクション','Collection','collection',
                 '名作選','秀作集','短篇集','短編傑作']
def is_collection(native):
    """短編集/全集 native か (= 個別作品が集約される 粒度ミスマッチ source)"""
    if not native: return False
    for p in COLL_PATTERNS:
        if p in native: return True
    if native.endswith('集') and not native.endswith('特集') and not native.endswith('編集'):
        return True
    return False

def en_norm_loose(s):
    if not s: return ''
    s = s.lower().replace('&','and')
    s = re.sub(r"['’‘]", '', s)
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', '', s)
    return s

def score_match(s3_year, s3_vols, sa_year, sa_vols, sa_format, n_channels,
                s3_authors, sa_authors, s3_asort, sa_asort,
                s3_authors_weak, s3_asort_weak, s3_en, sa_en):
    """v9 = v8 + 加点 signal (= key著者/en、 不一致では減点しない)。 returns (score, reasons[])"""
    if sa_format == 'NOVEL':
        return -200, ['format=NOVEL_reject']
    score = 100
    reasons = ['title_hit']
    # multi-channel
    if n_channels >= 4: score += 50; reasons.append('ch4+50')
    elif n_channels == 3: score += 30; reasons.append('ch3+30')
    elif n_channels == 2: score += 15; reasons.append('ch2+15')
    # author signal: 種2 master (= 高品質) → 一致+60/不一致-40
    author_done = False
    if s3_authors and sa_authors:
        if author_match(s3_authors, s3_asort, sa_authors, sa_asort):
            score += 60; reasons.append('author_match+60'); author_done = True
        else:
            score -= 40; reasons.append('author_MISMATCH-40'); author_done = True
    # key著者 (= MADB欄、 低品質) → 一致時のみ+40、 不一致は減点なし
    if not author_done and s3_authors_weak and sa_authors:
        if author_match(s3_authors_weak, s3_asort_weak, sa_authors, set()):
            score += 40; reasons.append('keyauthor_match+40')
    # en 完全/軽微一致 → +40 (= 確実な裏取り、 不一致は減点なし)
    if s3_en and sa_en and en_norm_loose(s3_en) == en_norm_loose(sa_en):
        score += 40; reasons.append('en_match+40')
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
        name_parts = [p[5:] for p in key.split('|') if p.startswith('name:')]
        if not name_parts: continue
        title = name_parts[-1]
        # key の name:著者 (= 最後=タイトル を除く) を weak author に
        weak_auth = set(); weak_asort = set()
        for nm in name_parts[:-1]:
            an = author_norm(nm)
            if an:
                weak_auth.add(an)
                ak = author_sortkey(an)
                if ak: weak_asort.add(ak)
        kana = entry.get('title_kana') or ''
        at = entry.get('alternative_titles') or {}
        en3 = (at.get('en') if isinstance(at, dict) else None) or ''
        shu3_entries.append({
            'key': key, 'title': title, 'kana': kana, 'en3': en3,
            'tn': title_norm(title), 'kn': kata_norm(kana),
            'year': sk_year.get(key), 'vols': sk_vols.get(key),
            'authors': sk_authors.get(key, set()),
            'asort': sk_asort.get(key, set()),
            'weak_auth': weak_auth, 'weak_asort': weak_asort,
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

    print('v9: 候補生成 (短編集除外含む)...', flush=True)
    total = len(shu3_entries)
    s3_cands = [[] for _ in range(total)]  # si → [(score, ei, reason, chs)]
    s3_had_channel = [False] * total       # title/kana で 候補が 1つでもあったか
    coll_excluded = 0
    pairs = []  # (score, si, ei, reason, chs)
    for si, s in enumerate(shu3_entries):
        cand_channels = defaultdict(set)
        if s['tn']:
            for ei in idx_a.get(s['tn'], []): cand_channels[ei].add('A')
        if s['kn']:
            for ei in idx_b.get(s['kn'], []): cand_channels[ei].add('B')
            for ei in idx_c.get(s['kn'], []): cand_channels[ei].add('C')
            for ei in idx_d.get(s['kn'], []): cand_channels[ei].add('D')
        if cand_channels:
            s3_had_channel[si] = True
        for ei, chs in cand_channels.items():
            e = entries[ei]
            # 短編集除外: 種a が短編集 かつ 種3 が個別作品
            if is_collection(e['native']) and not is_collection(s['title']):
                coll_excluded += 1
                continue
            sc, rs = score_match(s['year'], s['vols'], e['year'], e['vols'],
                                 e['format'], len(chs), s['authors'], e['authors'],
                                 s['asort'], e['asort'],
                                 s['weak_auth'], s['weak_asort'], s['en3'], e['en'])
            if sc < 100:
                continue
            s3_cands[si].append((sc, ei, rs, chs))
            pairs.append((sc, si, ei, rs, chs))
    print(f'  候補ペア (score>=100): {len(pairs):,}  / 短編集除外: {coll_excluded:,}', flush=True)

    print('v9: greedy 1対1 割り当て...', flush=True)
    # score 降順 (同点は si 昇順で安定化)
    pairs.sort(key=lambda x: (-x[0], x[1]))
    s3_assign = {}      # si → (score, ei, reason, chs)
    a_taken = set()
    for sc, si, ei, rs, chs in pairs:
        if si in s3_assign: continue
        if ei in a_taken: continue
        s3_assign[si] = (sc, ei, rs, chs)
        a_taken.add(ei)

    # ----- verdict 付与 + TSV dump -----
    def verdict_of(sc):
        if sc >= 180: return 'S180'
        if sc >= 150: return 'S150'
        if sc >= 130: return 'S130'
        return 'S100'
    OUT = '.cache/match-v9-all.tsv'
    cols = ['verdict','score','channels','reason',
            's3_key','s3_title','s3_kana','s3_year','s3_vols','s3_authors','s3_en',
            'a_id','a_native','a_en','a_romaji','a_year','a_vols','a_authors']
    def clean(x):
        return str(x).replace('\t',' ').replace('\n',' ').replace('\r',' ') if x is not None else ''
    cnt = defaultdict(int)
    score_hist = defaultdict(int)
    sig_keyauthor = sig_en = 0
    fo = open(OUT, 'w', encoding='utf-8', newline='')
    fo.write('\t'.join(cols) + '\n')
    for si, s in enumerate(shu3_entries):
        if si in s3_assign:
            sc, ei, rs, chs = s3_assign[si]
            e = entries[ei]
            v = verdict_of(sc)
            cnt[v] += 1
            score_hist[sc] += 1
            if 'keyauthor_match+40' in rs: sig_keyauthor += 1
            if 'en_match+40' in rs: sig_en += 1
            row = [v, sc, '+'.join(sorted(chs)), ','.join(rs),
                   s['key'], s['title'], s['kana'], s['year'] or '', s['vols'] or '',
                   '|'.join(sorted(s['authors'])), s['en3'],
                   e['id'], e['native'], e['en'], e['romaji'], e['year'] or '',
                   e['vols'] or '', '|'.join(sorted(e['authors']))]
        else:
            if s3_cands[si]:
                v = 'DISPLACED'   # 候補>=100 あったが 競合で 全敗
            elif s3_had_channel[si]:
                v = 'REJECT'      # 候補あったが 全て score<100
            else:
                v = 'NO_MATCH'    # title/kana で 候補ゼロ
            cnt[v] += 1
            row = [v, '', '', '', s['key'], s['title'], s['kana'], s['year'] or '',
                   s['vols'] or '', '|'.join(sorted(s['authors'])), s['en3'],
                   '','','','','','','']
        fo.write('\t'.join(clean(x) for x in row) + '\n')
    fo.close()

    accepted = cnt['S180']+cnt['S150']+cnt['S130']+cnt['S100']
    print()
    print(f'=== v9 全件マッチ状況 ({total:,} 種3 entries) ===  TSV: {OUT}')
    print(f'  S180 (鉄壁)      : {cnt["S180"]:,}')
    print(f'  S150             : {cnt["S150"]:,}')
    print(f'  S130             : {cnt["S130"]:,}')
    print(f'  S100             : {cnt["S100"]:,}')
    print(f'  ─ ACCEPT 計      : {accepted:,} ({accepted*100/total:.1f}%)')
    print(f'  DISPLACED(競合敗) : {cnt["DISPLACED"]:,}  ← 同一種a を 高score種3 に譲った')
    print(f'  REJECT(score<100): {cnt["REJECT"]:,}')
    print(f'  NO_MATCH         : {cnt["NO_MATCH"]:,}')
    print()
    print(f'=== 加点 signal が効いた件数 ===')
    print(f'  key著者一致 +40  : {sig_keyauthor:,}')
    print(f'  en軽微一致  +40  : {sig_en:,}')
    print()
    print(f'=== threshold 別 (v9, 競合解決後) ===')
    for th in (180, 150, 130):
        c = sum(cnt[x] for x in ('S180','S150','S130','S100') if int(x[1:]) >= th)
        print(f'  score >= {th}: {c:,} ({c*100/total:.1f}%)')
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
