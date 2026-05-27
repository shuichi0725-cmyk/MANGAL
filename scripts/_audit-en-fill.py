"""B 監査 = 外来語 en fill 漏れ統計。

種3 (series-supplement-v2.yml) から:
- alternative_titles.en が null の entry を抽出
- title (= key 末尾 name:<title>) の カタカナ純度別 tier に分類
- 各 tier の件数 + 巻数 (= 種2 sqlite から) 統計を出す

tier 定義:
  T1 = 完全カタカナ (= カタカナ + 記号/数字/英字 のみ)
  T2 = カタカナ + 助詞のみ (= の/に/と/は/を/が/で/も/や/へ/から/まで + カタカナ)
  T3 = カタカナ混在 (= カタカナ あるが 漢字/その他 ひらがな も含む)
  T4 = カタカナなし
"""
import yaml
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

YAML_PATH = Path('data/seeds/series-supplement-v2.yml')
SQLITE_PATH = Path('.cache/db.sqlite')

# 助詞 list (= T2 判定用)
PARTICLES = set('のにとはをがでもやへ')
PARTICLE_WORDS = {'から', 'まで', 'より', 'こそ', 'さえ', 'だけ', 'ばかり', 'など'}

KATAKANA_RE = re.compile(r'[゠-ヿㇰ-ㇿｦ-ﾟ]')
HIRAGANA_RE = re.compile(r'[぀-ゟ]')
KANJI_RE = re.compile(r'[一-鿿]')

def extract_title(key: str) -> str:
    """key 末尾の name:<title> から title を抽出。 sub: は除外。"""
    # split by |
    parts = key.split('|')
    # find last 'name:' segment (before any 'sub:')
    title_parts = [p[5:] for p in parts if p.startswith('name:')]
    if not title_parts:
        return ''
    return title_parts[-1]  # 末尾の name: が title

def classify_title(title: str) -> str:
    """T1 / T2 / T3 / T4 を返す。"""
    has_kata = bool(KATAKANA_RE.search(title))
    has_hira = bool(HIRAGANA_RE.search(title))
    has_kanji = bool(KANJI_RE.search(title))
    if not has_kata:
        return 'T4'
    if has_kanji:
        return 'T3'
    # has_kata, no kanji
    if not has_hira:
        return 'T1'
    # has_kata + has_hira
    # ひらがな部分が全部 助詞 なら T2
    hira_chars = HIRAGANA_RE.findall(title)
    # 連続 ひらがな 部分を抽出して 助詞語 だけかチェック
    hira_runs = re.findall(r'[぀-ゟ]+', title)
    for run in hira_runs:
        if len(run) == 1 and run in PARTICLES:
            continue
        if run in PARTICLE_WORDS:
            continue
        # 1 文字 か 2 文字以下 助詞 でなければ T3
        return 'T3'
    return 'T2'

def load_volume_counts():
    """種2 sqlite から qid -> 巻数 マップ取得。"""
    if not SQLITE_PATH.exists():
        return {}
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    # series テーブルの構造を確認
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f'[debug] sqlite tables: {tables}')
    # series_volumes など で 巻数 取得 想定
    # まず series_volumes が ある か
    if 'series_volumes' in tables:
        cur.execute("SELECT qid, COUNT(*) FROM series_volumes GROUP BY qid")
    elif 'volumes' in tables:
        cur.execute("SELECT qid, COUNT(*) FROM volumes WHERE qid IS NOT NULL GROUP BY qid")
    else:
        return {}
    counts = dict(cur.fetchall())
    conn.close()
    return counts

def extract_qid(key: str) -> str | None:
    for p in key.split('|'):
        if p.startswith('qid:'):
            return p[4:]
    return None

def main():
    print(f'loading {YAML_PATH}...')
    with YAML_PATH.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    series = data['series']
    print(f'total entries: {len(series)}')

    vol_counts = load_volume_counts()
    print(f'volume count entries: {len(vol_counts)}')

    # 統計
    en_null_count = 0
    en_filled_count = 0
    en_no_field_count = 0
    tier_counts = Counter()
    tier_en_null_counts = Counter()
    tier_volcounts = defaultdict(list)  # tier -> list of (qid, vol_count, title)
    tier_examples = defaultdict(list)

    for entry in series:
        key = entry.get('key', '')
        title = extract_title(key)
        if not title:
            continue
        tier = classify_title(title)
        tier_counts[tier] += 1

        alt = entry.get('alternative_titles') or {}
        en = alt.get('en') if isinstance(alt, dict) else None
        if 'alternative_titles' not in entry or not isinstance(alt, dict):
            en_no_field_count += 1
            has_en = False
        elif en is None or en == '':
            en_null_count += 1
            has_en = False
        else:
            en_filled_count += 1
            has_en = True

        if not has_en:
            tier_en_null_counts[tier] += 1
            qid = extract_qid(key)
            vc = vol_counts.get(qid, 0)
            tier_volcounts[tier].append((qid, vc, title))
            if len(tier_examples[tier]) < 10:
                tier_examples[tier].append((title, vc))

    print()
    print('=== en field 統計 ===')
    print(f'en filled: {en_filled_count}')
    print(f'en null (field exists): {en_null_count}')
    print(f'no alternative_titles field: {en_no_field_count}')
    print(f'total: {en_filled_count + en_null_count + en_no_field_count}')

    print()
    print('=== tier 別 全件数 ===')
    for t in ['T1', 'T2', 'T3', 'T4']:
        print(f'  {t}: {tier_counts[t]:,}')

    print()
    print('=== tier 別 en=null 件数 ===')
    for t in ['T1', 'T2', 'T3', 'T4']:
        print(f'  {t}: {tier_en_null_counts[t]:,}')

    print()
    print('=== tier 別 巻数 分布 (en=null のみ) ===')
    for t in ['T1', 'T2', 'T3', 'T4']:
        vols = [vc for _, vc, _ in tier_volcounts[t]]
        if not vols:
            continue
        vols_sorted = sorted(vols, reverse=True)
        total = sum(vols)
        with_vol = len([v for v in vols if v > 0])
        max_v = max(vols) if vols else 0
        print(f'  {t}: 件数={len(vols)}, 巻数累計={total}, 最大巻数={max_v}, 巻数あり={with_vol}')
        # 巻数分布
        if vols_sorted:
            print(f'    top10 巻数: {vols_sorted[:10]}')

    print()
    print('=== tier 別 examples (= top 10 en=null) ===')
    for t in ['T1', 'T2', 'T3', 'T4']:
        examples = sorted(tier_examples[t], key=lambda x: -x[1])[:10]
        print(f'  {t}:')
        for title, vc in examples:
            print(f'    [{vc:4d}vol] {title}')

    # 巻数 desc top 30 (T1+T2) を 出力 (= 優先 fill 候補)
    print()
    print('=== T1+T2 巻数 desc top 30 (= 優先 fill 候補) ===')
    combined = tier_volcounts['T1'] + tier_volcounts['T2']
    combined.sort(key=lambda x: -x[1])
    for qid, vc, title in combined[:30]:
        print(f'  [{vc:4d}vol] {qid:12s} {title}')

if __name__ == '__main__':
    main()
