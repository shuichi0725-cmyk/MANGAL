"""種3 (series-supplement-v2.yml) の 全 field 統計。

各 entry の field 出現 / 不在 / null / 空 を 網羅集計。
nested field (= alternative_titles.*) も 展開。
"""
import yaml
import sys
from pathlib import Path
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

YAML_PATH = Path('data/seeds/series-supplement-v2.yml')
OUT_PATH = Path('.cache/fields-audit.md')

def is_empty(v):
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == '':
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False

def main():
    with YAML_PATH.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    series = data['series']
    total = len(series)

    # 統計
    field_present = Counter()      # field が key として存在
    field_non_empty = Counter()    # 非 null / 非空 値
    field_null = Counter()         # null
    field_empty = Counter()        # 空文字 / 空 list / 空 dict
    # nested (= alternative_titles の sub key)
    alt_present = Counter()
    alt_non_empty = Counter()

    all_field_keys = set()
    sample_values = defaultdict(list)

    for entry in series:
        for k, v in entry.items():
            all_field_keys.add(k)
            field_present[k] += 1
            if is_empty(v):
                if v is None:
                    field_null[k] += 1
                else:
                    field_empty[k] += 1
            else:
                field_non_empty[k] += 1
                if len(sample_values[k]) < 5:
                    sample_values[k].append(repr(v)[:80])
        # alternative_titles の sub-key を 展開
        alt = entry.get('alternative_titles')
        if isinstance(alt, dict):
            for ak, av in alt.items():
                alt_present[ak] += 1
                if not is_empty(av):
                    alt_non_empty[ak] += 1

    # field 説明
    field_doc = {
        'key': '一意 ID (= "qid:Q...|name:<title>|sub:<subtitle>" or "name:<author>|name:<title>")',
        'title_kana': 'フリガナ (= カタカナ表記、 連結形)',
        'title_kana_segmented': 'フリガナ スペース区切り (= HP 表示用 / sort 用)',
        'subtitle_kana': 'サブタイトル フリガナ (= subtitle あれば)',
        'subtitle_kana_segmented': 'サブタイトル フリガナ スペース区切り',
        'magazine': '掲載誌 (= 週刊少年マガジン 等)',
        'demographic': '読者層 (= shounen / shoujo / seinen / josei / kodomo)',
        'genres': 'ジャンルタグ list (= action, romance 等、 genres.yml 参照)',
        'synopsis': 'あらすじ (= 1-2 文 簡潔説明)',
        'status': '連載状態 (= ongoing / completed / hiatus 等)',
        'anime_adapted': 'アニメ化済 (= boolean)',
        'alternative_titles': '別タイトル dict (= en, romaji 等)',
        'slug': 'URL slug 手動 override (= optional)',
    }

    alt_doc = {
        'en': '英語タイトル (= "One Piece", "Demon Slayer" 等。 slug 生成で 優先採用)',
        'romaji': 'ローマ字表記 (= フリガナ の ローマ字版、 optional)',
        'ja': '日本語別表記 (= 旧表記 等、 optional)',
    }

    lines = []
    lines.append('# 種3 (series-supplement-v2.yml) field 統計\n')
    lines.append(f'\n- **総 entry 数**: {total:,}\n')
    lines.append(f'- **抽出日**: 2026-05-28\n')
    lines.append(f'- **対象**: `data/seeds/series-supplement-v2.yml`\n\n')

    lines.append('## トップレベル field\n\n')
    lines.append('| field | 出現 | 非空 | null | 空 | 不在 | 不在% | 意味 |\n')
    lines.append('|---|---:|---:|---:|---:|---:|---:|---|\n')
    for k in sorted(all_field_keys):
        p = field_present[k]
        ne = field_non_empty[k]
        nu = field_null[k]
        em = field_empty[k]
        absent = total - p
        absent_pct = absent * 100 / total
        doc = field_doc.get(k, '(未知 field)')
        lines.append(f'| `{k}` | {p:,} | {ne:,} | {nu:,} | {em:,} | {absent:,} | {absent_pct:.1f}% | {doc} |\n')

    lines.append('\n## `alternative_titles` 内 sub-field\n\n')
    lines.append('| sub-field | 出現 | 非空 | 意味 |\n')
    lines.append('|---|---:|---:|---|\n')
    for k in sorted(alt_present.keys()):
        p = alt_present[k]
        ne = alt_non_empty[k]
        doc = alt_doc.get(k, '(未知 sub-field)')
        lines.append(f'| `{k}` | {p:,} | {ne:,} | {doc} |\n')

    lines.append('\n## 各 field sample 値\n\n')
    for k in sorted(all_field_keys):
        lines.append(f'### `{k}`\n\n')
        for v in sample_values[k][:5]:
            lines.append(f'- `{v}`\n')
        lines.append('\n')

    OUT_PATH.write_text(''.join(lines), encoding='utf-8')
    print(f'wrote {OUT_PATH}')
    print(f'total entries: {total}')
    print(f'top-level fields: {len(all_field_keys)}')
    print(f'alt sub-fields: {len(alt_present)}')

if __name__ == '__main__':
    main()
