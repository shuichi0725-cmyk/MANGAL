"""phonetic match audit = 種3 title_kana ⇔ 種a romaji 変換 katakana。

戦略:
  種3 title_kana を 「kata norm」 (= スペース除去 + lowercase) で保持
  種a title.romaji を Hepburn → katakana 変換 → 「kata norm」
  両者 match で 不一致 native title でも 同作品判定

Hepburn → katakana 変換:
  - 拗音 (kya/sha/cha 等) を先に処理
  - 促音 (kk/ss/tt 等) → ッ + 子音
  - 長音 (ou/uu/ei 等) → 母音 + ー
  - 単音節 (ka/ki/ku 等)
"""
import sys, gzip, json, yaml, re
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict
from pathlib import Path

# --- Hepburn → Katakana 変換 ---

# 拗音 (= 3 文字、 最優先) / 促音含む2文字 / 単音節 の順で処理
# まず長音以外の音節を 列挙
SYL_3 = {
    'kya': 'キャ', 'kyu': 'キュ', 'kyo': 'キョ',
    'gya': 'ギャ', 'gyu': 'ギュ', 'gyo': 'ギョ',
    'sha': 'シャ', 'shu': 'シュ', 'sho': 'ショ', 'shi': 'シ',
    'cha': 'チャ', 'chu': 'チュ', 'cho': 'チョ', 'chi': 'チ',
    'ja': 'ジャ', 'ju': 'ジュ', 'jo': 'ジョ',
    'nya': 'ニャ', 'nyu': 'ニュ', 'nyo': 'ニョ',
    'hya': 'ヒャ', 'hyu': 'ヒュ', 'hyo': 'ヒョ',
    'bya': 'ビャ', 'byu': 'ビュ', 'byo': 'ビョ',
    'pya': 'ピャ', 'pyu': 'ピュ', 'pyo': 'ピョ',
    'mya': 'ミャ', 'myu': 'ミュ', 'myo': 'ミョ',
    'rya': 'リャ', 'ryu': 'リュ', 'ryo': 'リョ',
    'tsu': 'ツ',
}
SYL_2 = {
    'ka': 'カ', 'ki': 'キ', 'ku': 'ク', 'ke': 'ケ', 'ko': 'コ',
    'ga': 'ガ', 'gi': 'ギ', 'gu': 'グ', 'ge': 'ゲ', 'go': 'ゴ',
    'sa': 'サ', 'su': 'ス', 'se': 'セ', 'so': 'ソ',
    'za': 'ザ', 'ji': 'ジ', 'zu': 'ズ', 'ze': 'ゼ', 'zo': 'ゾ',
    'ta': 'タ', 'te': 'テ', 'to': 'ト',
    'da': 'ダ', 'de': 'デ', 'do': 'ド',
    'na': 'ナ', 'ni': 'ニ', 'nu': 'ヌ', 'ne': 'ネ', 'no': 'ノ',
    'ha': 'ハ', 'hi': 'ヒ', 'fu': 'フ', 'he': 'ヘ', 'ho': 'ホ',
    'ba': 'バ', 'bi': 'ビ', 'bu': 'ブ', 'be': 'ベ', 'bo': 'ボ',
    'pa': 'パ', 'pi': 'ピ', 'pu': 'プ', 'pe': 'ペ', 'po': 'ポ',
    'ma': 'マ', 'mi': 'ミ', 'mu': 'ム', 'me': 'メ', 'mo': 'モ',
    'ya': 'ヤ', 'yu': 'ユ', 'yo': 'ヨ',
    'ra': 'ラ', 'ri': 'リ', 'ru': 'ル', 're': 'レ', 'ro': 'ロ',
    'wa': 'ワ', 'wo': 'ヲ',
    'va': 'ヴァ', 'vi': 'ヴィ', 'vu': 'ヴ', 've': 'ヴェ', 'vo': 'ヴォ',
    'fa': 'ファ', 'fi': 'フィ', 'fe': 'フェ', 'fo': 'フォ',
    'ti': 'ティ', 'di': 'ディ', 'tu': 'トゥ', 'du': 'ドゥ',
}
SYL_1 = {
    'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ',
    'n': 'ン',
}

CONSONANTS = set('kgsztcdnhfbpmyrwvj')

def hepburn_to_kata(s: str) -> str:
    if not s: return ''
    s = s.lower()
    # 非英字 文字 (= 漢字/カタカナ等) はそのまま keep
    # 空白除去
    s = re.sub(r'[\s　]+', ' ', s)
    # 「-」 (= long sound) → ー
    s = s.replace('-', '')
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        # 非 ASCII (= 漢字/カナ/記号) はそのまま
        if not c.isascii():
            out.append(c)
            i += 1
            continue
        # ASCII non-alphabetic (= 数字/記号) はそのまま
        if not c.isalpha():
            i += 1
            continue
        # 促音 (= 「kka」 「ssa」 「tte」 等) - 子音重複
        if i + 1 < len(s) and c == s[i+1] and c in CONSONANTS:
            out.append('ッ')
            i += 1
            continue
        # 3 文字音節
        if i + 3 <= len(s):
            tri = s[i:i+3]
            if tri in SYL_3:
                out.append(SYL_3[tri])
                i += 3
                continue
        # 2 文字音節
        if i + 2 <= len(s):
            di = s[i:i+2]
            if di in SYL_2:
                out.append(SYL_2[di])
                i += 2
                continue
            # 「ou」 「uu」 「ei」 等 長音 → 後で 母音 + ー
        # 1 文字音節 (= 母音 / n)
        if c in SYL_1:
            out.append(SYL_1[c])
            i += 1
            continue
        # 未知の子音 - skip
        i += 1
    return ''.join(out)

def kata_norm(s: str) -> str:
    """katakana norm: スペース除去 + lowercase"""
    if not s: return ''
    s = re.sub(r'[\s　ー]+', '', s)
    return s

def title_norm(s: str) -> str:
    """既存 native title normalize"""
    if not s: return ''
    for p in [r'〜[^〜]*〜', r'～[^～]*～', r'-[^-]{2,}-', r'\([^)]*\)', r'（[^）]*）']:
        s = re.sub(p, '', s)
    s = re.sub(r'[:：].*$', '', s)
    for sep in ['・', '·', '·']:
        s = s.replace(sep, '')
    return re.sub(r'[\s　]+', '', s).strip().lower()

def main():
    print('loading 種3...', flush=True)
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    shu3_native_norms = set()
    shu3_kana_norms = set()
    shu3_kana_map = {}  # kana_norm → 代表 title (debug)
    total_shu3 = 0
    for entry in data['series']:
        key = entry.get('key', '')
        parts = key.split('|')
        title_parts = [p[5:] for p in parts if p.startswith('name:')]
        if not title_parts: continue
        total_shu3 += 1
        title = title_parts[-1]
        nn = title_norm(title)
        if nn: shu3_native_norms.add(nn)
        kana = entry.get('title_kana') or ''
        kn = kata_norm(kana)
        if kn:
            shu3_kana_norms.add(kn)
            if kn not in shu3_kana_map:
                shu3_kana_map[kn] = title
    print(f'  種3 entries: {total_shu3:,}, unique native norm: {len(shu3_native_norms):,}, unique kana norm: {len(shu3_kana_norms):,}', flush=True)

    print('loading 種a + 変換...', flush=True)
    shua_native_norms = set()  # 既存 native match
    shua_phonetic_kata_norms = set()  # romaji → kata → norm
    total_shua = 0
    sample_conversions = []
    with gzip.open('.cache/anilist-manga-dump.jsonl.gz', 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            total_shua += 1
            t = e.get('title') or {}
            # native (+ synonyms) normalize
            for c in [t.get('native'), t.get('english')]:
                if c:
                    n = title_norm(c)
                    if n: shua_native_norms.add(n)
            for syn in (e.get('synonyms') or []):
                if syn:
                    n = title_norm(syn)
                    if n: shua_native_norms.add(n)
            # romaji → katakana 変換
            romaji = t.get('romaji') or ''
            if romaji:
                # subtitle 除去 (= 「:」 で切る、 「-」 連続 で切る)
                r = romaji.split(':')[0].strip()
                # 「 - 」 (= dash subtitle) で切る
                r = re.sub(r'\s+-\s+.*$', '', r)
                kata = hepburn_to_kata(r)
                kn = kata_norm(kata)
                if kn and len(kn) >= 3:
                    shua_phonetic_kata_norms.add(kn)
                    if len(sample_conversions) < 10:
                        sample_conversions.append((romaji, kata, kn))

    print(f'  種a entries: {total_shua:,}', flush=True)
    print(f'  native norm: {len(shua_native_norms):,}', flush=True)
    print(f'  phonetic kata norm: {len(shua_phonetic_kata_norms):,}', flush=True)
    print()
    print('=== 変換 sample ===')
    for ro, ka, kn in sample_conversions[:10]:
        print(f'  {ro!r:50s} → {ka!r:30s} → norm: {kn!r}')
    print()

    # 既存 native マッチ
    native_match = shu3_native_norms & shua_native_norms
    print(f'既存 native match: {len(native_match):,} unique norms')

    # phonetic マッチ (= 種3 title_kana ⇔ 種a romaji 変換 katakana)
    phonetic_match = shu3_kana_norms & shua_phonetic_kata_norms
    print(f'phonetic match: {len(phonetic_match):,} unique kana norms')

    # 統合 (両方の経路で マッチ)
    print()
    # 既存 native マッチした 種3 entries の native norm 集合
    print('=== 統合 ===')
    # 種3 entries で 統合マッチ算出 (= native or kana 経路で 種a に該当)
    matched_titles = 0
    only_phonetic = 0
    only_native = 0
    both = 0
    for entry in data['series']:
        parts = entry.get('key', '').split('|')
        title_parts = [p[5:] for p in parts if p.startswith('name:')]
        if not title_parts: continue
        title = title_parts[-1]
        nn = title_norm(title)
        kana = entry.get('title_kana') or ''
        kn = kata_norm(kana)
        in_native = nn in shua_native_norms if nn else False
        in_phonetic = kn in shua_phonetic_kata_norms if kn else False
        if in_native and in_phonetic:
            matched_titles += 1
            both += 1
        elif in_native:
            matched_titles += 1
            only_native += 1
        elif in_phonetic:
            matched_titles += 1
            only_phonetic += 1
    print(f'種3 全 entries: {total_shu3:,}')
    print(f'  統合 マッチ: {matched_titles:,} ({matched_titles*100/total_shu3:.1f}%)')
    print(f'    native のみ: {only_native:,}')
    print(f'    phonetic のみ (= ★新規拾い): {only_phonetic:,}')
    print(f'    両方: {both:,}')
    print(f'  非マッチ: {total_shu3 - matched_titles:,}')

if __name__ == '__main__':
    main()
