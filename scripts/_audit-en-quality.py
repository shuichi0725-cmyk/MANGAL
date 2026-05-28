"""en 品質監査 step 1 = 全件評価 + 分類。

種3 (series-supplement-v2.yml) の en filled entry を:
  - title_kana → 簡易ローマ字化
  - 既存 en と 類似度計算 (= ローマ字読み確度)
  - score 別に 自動OK / 要確認 / 要修正 に分類

出力:
  - 統計 (= 件数分布)
  - bucket 別 example
  - .cache/en-audit-suspicious.json = 要確認 + 要修正 リスト
"""
import yaml
import re
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter, defaultdict

# Force UTF-8 stdout (avoid cp932 errors on Windows)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

YAML_PATH = Path('data/seeds/series-supplement-v2.yml')
OUT_PATH = Path('.cache/en-audit-suspicious.json')

# Katakana → Romaji (Hepburn-ish, simplified)
KATA = {
    # basic vowels
    'ア':'a','イ':'i','ウ':'u','エ':'e','オ':'o',
    # k
    'カ':'ka','キ':'ki','ク':'ku','ケ':'ke','コ':'ko',
    'ガ':'ga','ギ':'gi','グ':'gu','ゲ':'ge','ゴ':'go',
    # s
    'サ':'sa','シ':'shi','ス':'su','セ':'se','ソ':'so',
    'ザ':'za','ジ':'ji','ズ':'zu','ゼ':'ze','ゾ':'zo',
    # t
    'タ':'ta','チ':'chi','ツ':'tsu','テ':'te','ト':'to',
    'ダ':'da','ヂ':'ji','ヅ':'zu','デ':'de','ド':'do',
    # n
    'ナ':'na','ニ':'ni','ヌ':'nu','ネ':'ne','ノ':'no',
    # h
    'ハ':'ha','ヒ':'hi','フ':'fu','ヘ':'he','ホ':'ho',
    'バ':'ba','ビ':'bi','ブ':'bu','ベ':'be','ボ':'bo',
    'パ':'pa','ピ':'pi','プ':'pu','ペ':'pe','ポ':'po',
    # m
    'マ':'ma','ミ':'mi','ム':'mu','メ':'me','モ':'mo',
    # y
    'ヤ':'ya','ユ':'yu','ヨ':'yo',
    # r
    'ラ':'ra','リ':'ri','ル':'ru','レ':'re','ロ':'ro',
    # w
    'ワ':'wa','ヲ':'wo','ン':'n',
    # v
    'ヴ':'vu',
    # small
    'ァ':'a','ィ':'i','ゥ':'u','ェ':'e','ォ':'o',
    'ャ':'ya','ュ':'yu','ョ':'yo',
    'ー':'',  # 長音
    'ッ':'',  # 促音 (handled specially)
    'ヮ':'wa',
}

SMALL_YA = {'ャ':'ya','ュ':'yu','ョ':'yo'}

def katakana_to_romaji(text: str) -> str:
    out = []
    i = 0
    chars = list(text)
    while i < len(chars):
        c = chars[i]
        # 促音 (ッ) = double next consonant
        if c == 'ッ' and i + 1 < len(chars):
            nxt = chars[i + 1]
            r = KATA.get(nxt, '')
            if r and r[0] not in 'aiueo':
                out.append(r[0])
            i += 1
            continue
        # combo with small ya/yu/yo
        if i + 1 < len(chars) and chars[i + 1] in SMALL_YA:
            base = KATA.get(c, '')
            small = SMALL_YA[chars[i + 1]]
            if base.endswith('i') and len(base) > 1:
                # ki + ya → kya
                out.append(base[:-1] + small)
            elif base:
                out.append(base + small)
            i += 2
            continue
        r = KATA.get(c, None)
        if r is not None:
            out.append(r)
        elif re.match(r'[A-Za-z0-9]', c):
            out.append(c.lower())
        # ignore kanji, hiragana, symbols
        i += 1
    return ''.join(out)

def normalize_for_compare(s: str) -> str:
    """lowercase + alphanumeric only"""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def similarity(a: str, b: str) -> float:
    na, nb = normalize_for_compare(a), normalize_for_compare(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()

def extract_title(key: str) -> str:
    parts = key.split('|')
    title_parts = [p[5:] for p in parts if p.startswith('name:')]
    return title_parts[-1] if title_parts else ''

def extract_qid(key: str) -> str | None:
    for p in key.split('|'):
        if p.startswith('qid:'):
            return p[4:]
    return None

def classify(sim: float, title: str, en: str) -> str:
    en_len = len(normalize_for_compare(en))
    title_kata_len = len(re.findall(r'[゠-ヿ]', title))
    # 自動 OK 条件:
    if en_len <= 4:
        return 'auto_ok_short'
    if title_kata_len == 0:
        # title に カタカナ無 = 漢字+ひらがな → en は意訳のはず、 ローマ字読みでない
        return 'auto_ok_no_kata'
    # 類似度ベース
    if sim >= 0.85:
        return 'fix_romaji'  # 要修正 = ローマ字読み確実
    if sim >= 0.70:
        return 'review_high'  # 要確認 高
    if sim >= 0.55:
        return 'review_mid'  # 要確認 中
    return 'auto_ok_natural'

def main():
    with YAML_PATH.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    series = data['series']

    buckets = defaultdict(list)
    sim_histogram = Counter()

    for entry in series:
        key = entry.get('key', '')
        title = extract_title(key)
        if not title:
            continue
        alt = entry.get('alternative_titles')
        en = alt.get('en') if isinstance(alt, dict) else None
        if not en:
            continue
        title_kana = entry.get('title_kana', '') or ''
        # Predict romaji from title_kana (= what AI fill would do)
        romaji_pred = katakana_to_romaji(title_kana)
        sim = similarity(romaji_pred, en)
        bucket = classify(sim, title, en)
        sim_bin = round(sim, 1)
        sim_histogram[sim_bin] += 1
        buckets[bucket].append({
            'qid': extract_qid(key),
            'key': key,
            'title': title,
            'title_kana': title_kana,
            'romaji_pred': romaji_pred,
            'en': en,
            'sim': round(sim, 3),
        })

    print('=== bucket 統計 ===')
    total = sum(len(v) for v in buckets.values())
    for b in ['auto_ok_short', 'auto_ok_no_kata', 'auto_ok_natural',
              'review_mid', 'review_high', 'fix_romaji']:
        n = len(buckets[b])
        pct = n * 100 / total if total else 0
        print(f'  {b:20s}: {n:6,d} ({pct:5.1f}%)')
    print(f'  {"TOTAL":20s}: {total:6,d}')

    print()
    print('=== 類似度ヒストグラム ===')
    for bin in sorted(sim_histogram.keys()):
        n = sim_histogram[bin]
        bar = '#' * int(n / 200)
        print(f'  sim {bin:.1f}: {n:6,d} {bar}')

    print()
    print('=== examples (= fix_romaji top 30) ===')
    fixes = sorted(buckets['fix_romaji'], key=lambda x: -x['sim'])[:30]
    for e in fixes:
        print(f"  sim={e['sim']:.2f} title={e['title'][:30]:30s} en={e['en'][:50]}")

    print()
    print('=== examples (= review_high top 30) ===')
    rh = sorted(buckets['review_high'], key=lambda x: -x['sim'])[:30]
    for e in rh:
        print(f"  sim={e['sim']:.2f} title={e['title'][:30]:30s} en={e['en'][:50]}")

    print()
    print('=== examples (= review_mid top 30) ===')
    rm = sorted(buckets['review_mid'], key=lambda x: -x['sim'])[:30]
    for e in rm:
        print(f"  sim={e['sim']:.2f} title={e['title'][:30]:30s} en={e['en'][:50]}")

    # Write 要確認/要修正 to json for next step
    suspicious = buckets['fix_romaji'] + buckets['review_high'] + buckets['review_mid']
    suspicious.sort(key=lambda x: -x['sim'])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open('w', encoding='utf-8') as f:
        json.dump(suspicious, f, ensure_ascii=False, indent=2)
    print(f'\n→ {OUT_PATH} に {len(suspicious)} 件出力')

if __name__ == '__main__':
    main()
