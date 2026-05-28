"""誤マッチ (FP) 推定。

approach:
  各 channel の マッチに対し、 種a 側 detail (= english, native, romaji, format,
  format = MANGA か NOVEL か、 startDate) を 引いて 「明らかに別作品」 確認。

特に厳しく見るべき pattern:
  - 短い title (= 4 字以下)
  - 一般語 (= Touch, Dolce, Alive, Cobra 等)
  - 種3 title (= ASCII) ↔ 種a (= 邦作カナ) で 別作品の可能性
"""
import sys, gzip, json, yaml, re
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict

# 既存 normalize 関数を inline で
PAREN_PATTERNS = [r'〜[^〜]*〜', r'～[^～]*～', r'\([^)]*\)', r'（[^）]*）']
SEPARATORS = ['・','·','·']

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

def main():
    # 種3 読み込み
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
            'title': title, 'kana': kana,
            'tn': title_norm(title), 'kn': kata_norm(kana),
        })

    # 種a 読み込み + index
    by_native_norm = defaultdict(list)
    by_native_kana = defaultdict(list)  # ひら→カタ 後
    by_synonyms_kana = defaultdict(list)
    by_phonetic_kata = defaultdict(list)

    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            t = e.get('title') or {}
            native = t.get('native') or ''
            en = t.get('english') or ''
            romaji = t.get('romaji') or ''
            entry_summary = {
                'native': native, 'en': en, 'romaji': romaji,
                'format': e.get('format'), 'isAdult': e.get('isAdult'),
                'syn': e.get('synonyms') or [],
                'startYear': (e.get('startDate') or {}).get('year'),
            }
            for c in [native, en]:
                n = title_norm(c)
                if n: by_native_norm[n].append(entry_summary)
            for syn in entry_summary['syn']:
                n = title_norm(syn)
                if n: by_native_norm[n].append(entry_summary)
            if native:
                kn = native_kana_form(native)
                if kn and len(kn) >= 2: by_native_kana[kn].append(entry_summary)
            for syn in entry_summary['syn']:
                kn = native_kana_form(syn)
                if kn and len(kn) >= 3: by_synonyms_kana[kn].append(entry_summary)

    # FP リスク分析:
    # 短い kana norm で channel C/D マッチ + 種a 側 別作品っぽい
    print('=== channel C で hit した entry の 1作種3↔多作種aケース 検出 ===')
    multi_hit_c = 0
    short_hit_c = 0
    sample_short = []
    sample_multi = []
    for s in shu3_entries:
        if not s['kn']: continue
        if s['tn'] in by_native_norm: continue  # A で取れる → C 純増ではない
        candidates = by_native_kana.get(s['kn'], [])
        if not candidates: continue
        # 短い (= 4 字以下) で C のみ hit
        if len(s['kn']) <= 4:
            short_hit_c += 1
            if len(sample_short) < 15:
                sample_short.append((s['title'], s['kana'], s['kn'], len(candidates), candidates[:2]))
        # 種a 側 同 kn に 2+ entries (= 同名異作品多数)
        if len(candidates) >= 2:
            multi_hit_c += 1
            if len(sample_multi) < 15:
                sample_multi.append((s['title'], s['kana'], s['kn'], candidates))

    print(f'  短い kana norm (=≤4字) で C only hit: {short_hit_c:,}')
    for ti, ka, kn, n, cand in sample_short[:10]:
        e1 = cand[0]
        print(f'    {ti!r} kana={ka!r} kn={kn!r}  → 種a {n}件: native={e1["native"]!r} en={e1["en"]!r} format={e1["format"]} yr={e1["startYear"]}')
    print()
    print(f'  種a 同 kn に 2+ entries で C only hit: {multi_hit_c:,}')
    for ti, ka, kn, cand in sample_multi[:10]:
        print(f'    {ti!r} kana={ka!r} kn={kn!r}  → 種a {len(cand)}件:')
        for e in cand[:3]:
            print(f'      - native={e["native"]!r} en={e["en"]!r} format={e["format"]} yr={e["startYear"]}')

    # 全体 multi-channel confirmation 統計
    print()
    print('=== マルチ-channel 確証 (= 複数 channel で 同一作品判定) 強度分析 ===')
    by_strength = defaultdict(int)  # n channels → count
    for s in shu3_entries:
        in_a = s['tn'] in by_native_norm if s['tn'] else False
        in_c = s['kn'] in by_native_kana if s['kn'] else False
        in_d = s['kn'] in by_synonyms_kana if s['kn'] else False
        n_hits = sum([in_a, in_c, in_d])
        by_strength[n_hits] += 1
    for n in sorted(by_strength.keys(), reverse=True):
        print(f'  {n} channels hit: {by_strength[n]:,}')

    # 「種a 側 ambiguous (= 同 norm に複数 entries)」 統計
    print()
    print('=== 種a 側 ambiguous norm 統計 ===')
    a_amb = sum(1 for v in by_native_norm.values() if len(v) >= 2)
    c_amb = sum(1 for v in by_native_kana.values() if len(v) >= 2)
    print(f'  channel A index: {len(by_native_norm):,}, 内 ambiguous (= 2+ entries 共有): {a_amb:,}')
    print(f'  channel C index: {len(by_native_kana):,}, 内 ambiguous: {c_amb:,}')

if __name__ == '__main__':
    main()
