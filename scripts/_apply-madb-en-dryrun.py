"""種1 の title_official_en (= MADB 公式英訳) を 種3 v2 に 上書き適用 [DRY RUN]。

key で マッチさせて、 公式英訳がある entry の en を 上書き予定として 集計 + サンプル出力。
"""
import yaml
import sys
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

QUEUE = Path('data/seeds/_ai-fill-queue.yml')
V2 = Path('data/seeds/series-supplement-v2.yml')
OUT_SAMPLES = Path('.cache/madb-en-overwrite-samples.md')

def main():
    print('loading _ai-fill-queue.yml...')
    with QUEUE.open('r', encoding='utf-8') as f:
        q = yaml.safe_load(f)
    queue_entries = q['entries']
    print(f'queue entries: {len(queue_entries)}')

    # title_official_en 持ち の key → official_en map
    official = {}
    for e in queue_entries:
        en = e.get('title_official_en')
        if en and en.strip():
            official[e['key']] = en.strip()
    print(f'公式英訳あり: {len(official)} 件')

    print('loading series-supplement-v2.yml...')
    with V2.open('r', encoding='utf-8') as f:
        v2 = yaml.safe_load(f)
    series = v2['series']
    print(f'v2 entries: {len(series)}')

    # マッチ + 上書き 集計
    v2_by_key = {e['key']: e for e in series}

    matched = 0
    unmatched = 0
    will_overwrite = 0  # 既存 en と異なる
    will_keep = 0       # 既存 en と同じ
    will_add = 0        # en field なし → 追加
    overwrite_samples = []

    for q_key, off_en in official.items():
        v2_entry = v2_by_key.get(q_key)
        if v2_entry is None:
            unmatched += 1
            continue
        matched += 1
        alt = v2_entry.get('alternative_titles')
        existing_en = None
        if isinstance(alt, dict):
            existing_en = alt.get('en')

        if existing_en is None:
            will_add += 1
            action = 'ADD'
        elif existing_en == off_en:
            will_keep += 1
            action = 'KEEP'
        else:
            will_overwrite += 1
            action = 'OVERWRITE'

        if action != 'KEEP' and len(overwrite_samples) < 50:
            # title 抽出
            parts = q_key.split('|')
            title_parts = [p[5:] for p in parts if p.startswith('name:')]
            title = title_parts[-1] if title_parts else q_key
            overwrite_samples.append({
                'action': action,
                'title': title,
                'existing': existing_en or '(none)',
                'official': off_en,
            })

    print(f'\n=== 集計 ===')
    print(f'  matched (= 種1 公式英訳 が 種3 にもある): {matched:,}')
    print(f'  unmatched (= 種1 だけにある): {unmatched:,}')
    print(f'  内訳:')
    print(f'    ADD (既存 en なし → 追加): {will_add:,}')
    print(f'    KEEP (既存 en = 公式英訳、 変更なし): {will_keep:,}')
    print(f'    OVERWRITE (既存 en ≠ 公式英訳、 上書き): {will_overwrite:,}')

    # サンプル出力 (markdown)
    lines = ['# 種1 → 種3 v2 公式英訳上書き dry-run\n\n']
    lines.append(f'- 種1 公式英訳: {len(official):,} 件\n')
    lines.append(f'- 種3 v2 と マッチ: {matched:,} 件\n')
    lines.append(f'- ADD: {will_add:,}, KEEP: {will_keep:,}, **OVERWRITE: {will_overwrite:,}**\n\n')
    lines.append('## サンプル (= ADD + OVERWRITE のみ、 最大 50 件)\n\n')
    lines.append('| action | title | 既存 en | 公式英訳 |\n')
    lines.append('|---|---|---|---|\n')
    for s in overwrite_samples:
        lines.append(f'| {s["action"]} | {s["title"]} | {s["existing"]} | {s["official"]} |\n')
    OUT_SAMPLES.write_text(''.join(lines), encoding='utf-8')
    print(f'\n→ {OUT_SAMPLES} に サンプル {len(overwrite_samples)} 件出力')

if __name__ == '__main__':
    main()
