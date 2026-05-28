"""種3 ↔ 種a 多channel match audit。

channels:
  A: 種3.title (native) norm ↔ 種a.{native, english, synonyms} norm
  B: 種3.title_kana ↔ 種a.romaji の Hepburn → katakana 変換 norm
  C: 種3.title_kana ↔ 種a.native の ひら→カタ 変換 norm (★新規)
  D: 種3.title_kana ↔ 種a.synonyms (= 日本語 synonyms 含むため、 ひら→カタ 変換) (★新規)

結果:
  各 channel 独立 + 統合 マッチ率
  channel C のみ で 拾える entries サンプル
"""
import sys, gzip, json, yaml, re
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

# --- Hepburn → Katakana (= channel B 用、 既存と同じ) ---
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

# --- ひら → カタ 変換 (= channel C/D 用) ---
def hira_to_kata(s):
    return ''.join(
        chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c
        for c in s
    )

# --- normalize ---
PAREN_PATTERNS = [r'〜[^〜]*〜', r'～[^～]*～', r'\([^)]*\)', r'（[^）]*）', r'\[[^\]]*\]', r'【[^】]*】']
SEPARATORS = ['・','·','·','⋅','•','∙','＝']

def title_norm(s):
    """既存 native title normalize"""
    if not s: return ''
    for p in PAREN_PATTERNS: s = re.sub(p, '', s)
    s = re.sub(r'[:：].*$', '', s)
    for sep in SEPARATORS: s = s.replace(sep, '')
    return re.sub(r'[\s　]+', '', s).strip().lower()

def kata_norm(s):
    """katakana 系 norm: 中黒/空白/長音 除去 + ASCII 大小無視"""
    if not s: return ''
    s = re.split(r'[:：]', s, 1)[0]
    for p in PAREN_PATTERNS: s = re.sub(p, '', s)
    for sep in SEPARATORS: s = s.replace(sep, '')
    s = re.sub(r'[\s　ー]+', '', s)
    return s.lower()

def native_to_kana_form(s):
    """native (= 種a) を 種3 title_kana 風 に: ひら→カタ + 上記 kata_norm"""
    if not s: return ''
    s = hira_to_kata(s)
    return kata_norm(s)

def main():
    print('loading 種3...', flush=True)
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    shu3_entries = []
    for entry in data['series']:
        key = entry.get('key', '')
        parts = key.split('|')
        title_parts = [p[5:] for p in parts if p.startswith('name:')]
        if not title_parts: continue
        title = title_parts[-1]
        kana = entry.get('title_kana') or ''
        shu3_entries.append({
            'title': title,
            'title_kana': kana,
            'tn': title_norm(title),
            'kn': kata_norm(kana),
        })
    total_shu3 = len(shu3_entries)
    print(f'  種3 entries: {total_shu3:,}', flush=True)

    print('loading 種a + 多 channel 変換...', flush=True)
    # 種a index per-channel
    idx_native = set()         # channel A target
    idx_phonetic = set()       # channel B target (= romaji → katakana)
    idx_native_kana = set()    # channel C target (= native ひら→カタ)
    idx_synonyms_kana = set()  # channel D target (= synonyms ひら→カタ)

    total_shua = 0
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            total_shua += 1
            t = e.get('title') or {}

            # Channel A: native + english + synonyms 直接 norm
            for c in [t.get('native'), t.get('english')]:
                if c:
                    n = title_norm(c)
                    if n: idx_native.add(n)
            for syn in (e.get('synonyms') or []):
                if syn:
                    n = title_norm(syn)
                    if n: idx_native.add(n)

            # Channel B: romaji → katakana (Hepburn)
            romaji = t.get('romaji') or ''
            if romaji:
                r = romaji.split(':')[0].strip()
                r = re.sub(r'\s+-\s+.*$', '', r)
                kn = kata_norm(hepburn_to_kata(r))
                if kn and len(kn) >= 3:
                    idx_phonetic.add(kn)

            # Channel C: native の ひら→カタ 変換
            native = t.get('native') or ''
            if native:
                kn = native_to_kana_form(native)
                if kn and len(kn) >= 2:
                    idx_native_kana.add(kn)

            # Channel D: synonyms の ひら→カタ 変換 (= 日本語別表記)
            for syn in (e.get('synonyms') or []):
                if syn:
                    kn = native_to_kana_form(syn)
                    if kn and len(kn) >= 3:
                        idx_synonyms_kana.add(kn)

    print(f'  種a entries: {total_shua:,}', flush=True)
    print(f'  channel A (native+en+syn norm): {len(idx_native):,}', flush=True)
    print(f'  channel B (romaji→katakana): {len(idx_phonetic):,}', flush=True)
    print(f'  channel C (native ひら→カタ): {len(idx_native_kana):,}', flush=True)
    print(f'  channel D (synonyms ひら→カタ): {len(idx_synonyms_kana):,}', flush=True)
    print()

    # 各 channel 独立 計測
    only_a = only_b = only_c = only_d = 0
    matched_by_any = 0
    new_by_c_samples = []
    new_by_d_samples = []
    new_by_c_or_d_samples = []
    by_channel_count = {'A': 0, 'B': 0, 'C': 0, 'D': 0}

    for s in shu3_entries:
        in_a = s['tn'] in idx_native if s['tn'] else False
        in_b = s['kn'] in idx_phonetic if s['kn'] else False
        in_c = s['kn'] in idx_native_kana if s['kn'] else False
        in_d = s['kn'] in idx_synonyms_kana if s['kn'] else False
        if in_a: by_channel_count['A'] += 1
        if in_b: by_channel_count['B'] += 1
        if in_c: by_channel_count['C'] += 1
        if in_d: by_channel_count['D'] += 1
        any_hit = in_a or in_b or in_c or in_d
        if any_hit:
            matched_by_any += 1
        # 「A+B 以外 (= C or D) でしか拾えない」 entries サンプル
        if not in_a and not in_b and (in_c or in_d):
            if len(new_by_c_or_d_samples) < 30:
                new_by_c_or_d_samples.append((s['title'], s['title_kana'], in_c, in_d))

    print('=== channel 個別 統計 ===')
    for ch, cnt in by_channel_count.items():
        print(f'  channel {ch} hit: {cnt:,} ({cnt*100/total_shu3:.1f}%)')
    print()
    print(f'=== 統合 (= A∪B∪C∪D 何かで hit) ===')
    print(f'  matched: {matched_by_any:,} / {total_shu3:,} ({matched_by_any*100/total_shu3:.1f}%)')
    print(f'  unmatched: {total_shu3 - matched_by_any:,}')
    print()
    print(f'=== A+B 既存で逃したが C or D で拾った サンプル (= 純増 {len([1 for s in shu3_entries if not (s["tn"] in idx_native if s["tn"] else False) and not (s["kn"] in idx_phonetic if s["kn"] else False) and ((s["kn"] in idx_native_kana if s["kn"] else False) or (s["kn"] in idx_synonyms_kana if s["kn"] else False))]):,}) ===')
    for title, kana, c, d in new_by_c_or_d_samples[:20]:
        ch_label = 'C+D' if (c and d) else 'C' if c else 'D'
        print(f'  [{ch_label}] {title!r:50s}  kana={kana!r}')

if __name__ == '__main__':
    main()
