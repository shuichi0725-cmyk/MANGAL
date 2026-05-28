"""種3 で adult filter 抜けたはずの entry が 種a (AniList) で isAdult 判定されているもの 検出。

照合: native title 完全一致 (= 種3 key 末尾 name: + 種a title.native)
出力: .cache/shu3-adult-leak.md (= 一覧表 + 件数)
"""
import sys, gzip, json, yaml, re
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SHU3 = Path('data/seeds/series-supplement-v2.yml')
DUMP = Path('.cache/anilist-manga-dump.jsonl.gz')
OUT = Path('.cache/shu3-adult-leak.md')

def normalize(s: str) -> str:
    return re.sub(r'\s+', '', (s or '').strip())

def extract_title(key: str) -> str:
    parts = key.split('|')
    title_parts = [p[5:] for p in parts if p.startswith('name:')]
    return title_parts[-1] if title_parts else ''

def main():
    # 種3 読み込み: native_title → list of (key, demographic, genres)
    print('loading 種3...')
    with SHU3.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    shu3_map = defaultdict(list)
    for entry in data['series']:
        key = entry.get('key', '')
        title = extract_title(key)
        if not title:
            continue
        n = normalize(title)
        shu3_map[n].append({
            'key': key, 'title': title,
            'demographic': entry.get('demographic'),
            'genres': entry.get('genres'),
        })
    print(f'  種3 unique titles: {len(shu3_map):,}')

    # 種a (AniList) 読み込み: isAdult=True の native_title → list
    print('loading 種a (= AniList dump)...')
    shua_adult = defaultdict(list)
    shua_total_adult = 0
    with gzip.open(DUMP, 'rt', encoding='utf-8') as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if not e.get('isAdult'):
                continue
            shua_total_adult += 1
            native = (e.get('title') or {}).get('native') or ''
            if not native:
                continue
            n = normalize(native)
            shua_adult[n].append({
                'id': e['id'],
                'native': native,
                'romaji': (e.get('title') or {}).get('romaji'),
                'english': (e.get('title') or {}).get('english'),
                'format': e.get('format'),
                'genres': e.get('genres'),
                'tags': [t.get('name') for t in (e.get('tags') or [])],
                'isAdult': e.get('isAdult'),
            })
    print(f'  種a adult entries: {shua_total_adult:,}, unique titles: {len(shua_adult):,}')

    # 突合 (= 共通 native title)
    common = set(shu3_map.keys()) & set(shua_adult.keys())
    print(f'\n[result] 種3 ∩ 種a(isAdult): {len(common):,} unique titles')

    # 種3 entry 数 (= subtitle 違い等 で 同 native に複数あり得る)
    total_shu3_entries = sum(len(shu3_map[n]) for n in common)
    print(f'  種3 entries (= subtitle 違い含む): {total_shu3_entries:,}')

    # 表生成 (= markdown)
    lines = [
        '# 種3 に居て 種a で isAdult=True の entry 一覧\n\n',
        f'- 種3 全 entries: 76,435 (= unique native titles: {len(shu3_map):,})\n',
        f'- 種a 全 entries: 101,590 (= isAdult=True: {shua_total_adult:,})\n',
        f'- **共通 native title: {len(common):,}**\n',
        f'- **対応する 種3 entry 数 (= subtitle 違い含む): {total_shu3_entries:,}**\n\n',
        '## 一覧 (= native title 順)\n\n',
        '| # | native title | 種3 demographic | 種3 genres | 種a format | 種a english | 種a tags 抜粋 |\n',
        '|---|---|---|---|---|---|---|\n',
    ]
    for i, n in enumerate(sorted(common), 1):
        shu3_entries = shu3_map[n]
        # 代表 entry (= 先頭)
        s3 = shu3_entries[0]
        shua_entries = shua_adult[n]
        sa = shua_entries[0]
        title = s3['title'][:30]
        demo = s3.get('demographic') or '-'
        genres_s3 = ','.join(s3.get('genres') or [])[:30]
        fmt_a = sa.get('format') or '-'
        en_a = (sa.get('english') or '')[:30]
        tags_a = ', '.join((sa.get('tags') or [])[:5])[:50]
        lines.append(f'| {i} | {title} | {demo} | {genres_s3} | {fmt_a} | {en_a} | {tags_a} |\n')

    OUT.write_text(''.join(lines), encoding='utf-8')
    print(f'\n→ {OUT}')
    print(f'  (= {len(common):,} 件の表)')

if __name__ == '__main__':
    main()
