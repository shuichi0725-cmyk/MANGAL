"""種3 ∩ 種a(isAdult) audit v2 = 強化 normalize + synonyms 突合。

改善点:
  - 中黒 ・ 除去
  - 〜...〜 / ～...～ / -...- / [...] subtitle 除去
  - : / ： 以降除去
  - 種a synonyms にも 種3 title が含まれる場合に hit
  - 全角/半角空白除去
  - ASCII 大小無視

出力:
  .cache/shu3-adult-leak-v2.md (= 表)
  .cache/shu3-adult-leak-v2-titles.txt
  .cache/shu3-adult-leak-v2-entries.csv
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
OUT_MD = Path('.cache/shu3-adult-leak-v2.md')
OUT_TXT = Path('.cache/shu3-adult-leak-v2-titles.txt')
OUT_CSV = Path('.cache/shu3-adult-leak-v2-entries.csv')

# 強化 normalize
PAREN_PATTERNS = [
    r'〜[^〜]*〜', r'～[^～]*～',         # 〜...〜
    r'-[^-]{2,}-', r'－[^－]{2,}－',     # -...- (= 2 文字以上で subtitle 想定、 ‐ 含む)
    r'\([^)]*\)', r'（[^）]*）',          # (...) and （...）
    r'\[[^\]]*\]', r'［[^］]*］',          # [...] and ［...］
    r'【[^】]*】',                         # 【...】
    r'《[^》]*》',                         # 《...》
]
SEPARATORS = ['・', '·', '·', '⋅', '•', '∙']

def normalize_strong(s: str) -> str:
    if not s: return ''
    s = s.strip()
    # subtitle / 括弧 除去
    for p in PAREN_PATTERNS:
        s = re.sub(p, '', s)
    # : 以降除去
    s = re.sub(r'[:：].*$', '', s)
    # 中黒除去
    for sep in SEPARATORS:
        s = s.replace(sep, '')
    # 空白除去
    s = re.sub(r'[\s　]+', '', s)
    # ASCII lowercase
    s = s.lower()
    return s

def extract_title(key: str) -> str:
    parts = key.split('|')
    title_parts = [p[5:] for p in parts if p.startswith('name:')]
    return title_parts[-1] if title_parts else ''

def main():
    # 種3
    print('loading 種3...', flush=True)
    with SHU3.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    shu3_by_norm = defaultdict(list)
    shu3_total = 0
    for entry in data['series']:
        key = entry.get('key', '')
        title = extract_title(key)
        if not title: continue
        shu3_total += 1
        n = normalize_strong(title)
        if not n: continue
        shu3_by_norm[n].append({
            'key': key, 'title': title,
            'demographic': entry.get('demographic'),
            'genres': entry.get('genres'),
        })
    print(f'  種3 entries: {shu3_total:,}, normalized unique: {len(shu3_by_norm):,}', flush=True)

    # 種a (isAdult only) - native + synonyms 両方で index
    print('loading 種a isAdult entries...', flush=True)
    shua_norm_to_entries = defaultdict(list)
    shua_adult_total = 0
    with gzip.open(DUMP, 'rt', encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except: continue
            if not e.get('isAdult'): continue
            shua_adult_total += 1
            t = e.get('title') or {}
            # native だけでなく synonyms + romaji も index に登録
            candidates = [t.get('native'), t.get('romaji'), t.get('english')]
            for syn in (e.get('synonyms') or []):
                candidates.append(syn)
            seen_norms = set()
            for c in candidates:
                if not c: continue
                n = normalize_strong(c)
                if n and n not in seen_norms:
                    shua_norm_to_entries[n].append(e)
                    seen_norms.add(n)
    print(f'  種a adult entries: {shua_adult_total:,}, normalized unique: {len(shua_norm_to_entries):,}', flush=True)

    # 突合
    common = set(shu3_by_norm.keys()) & set(shua_norm_to_entries.keys())
    print(f'\n[result-v2] 種3 ∩ 種a(isAdult) = {len(common):,} unique normalized titles', flush=True)
    total_shu3_entries = sum(len(shu3_by_norm[n]) for n in common)
    print(f'  対応 種3 entries: {total_shu3_entries:,}', flush=True)

    # 出力
    # title list
    lines_txt = []
    lines_csv = ['key,title']
    for n in sorted(common):
        for s3 in shu3_by_norm[n]:
            lines_txt.append(s3['title'])
            ke = s3['key'].replace('"', '""')
            ti = s3['title'].replace('"', '""')
            lines_csv.append(f'"{ke}","{ti}"')
    OUT_TXT.write_text('\n'.join(lines_txt) + '\n', encoding='utf-8')
    OUT_CSV.write_text('\n'.join(lines_csv) + '\n', encoding='utf-8')

    # markdown 表
    md = []
    md.append(f'# 種3 ∩ 種a(isAdult) audit v2 = 強化 normalize\n\n')
    md.append(f'- 種3 全 entries: {shu3_total:,}\n')
    md.append(f'- 種a adult entries: {shua_adult_total:,}\n')
    md.append(f'- **共通 normalized titles**: **{len(common):,}**\n')
    md.append(f'- **対応 種3 entries**: **{total_shu3_entries:,}**\n\n')
    md.append('## normalize ルール (適用順)\n\n')
    md.append('1. `〜...〜` `～...～` `-...-` `(...)` `[...]` `【...】` `《...》` 除去\n')
    md.append('2. `:` `：` 以降除去\n')
    md.append('3. 中黒 ・ 除去\n')
    md.append('4. 空白 (= 半角 + 全角 + tab) 除去\n')
    md.append('5. ASCII 大小無視\n\n')
    md.append('## v1 (= 弱 normalize) との 比較\n\n')
    md.append('| version | unique titles | 種3 entries |\n|---|---:|---:|\n')
    md.append(f'| v1 (= whitespace only) | 2,083 | 2,242 |\n')
    md.append(f'| **v2 (= 強化)** | **{len(common):,}** | **{total_shu3_entries:,}** |\n\n')
    md.append('## 一覧 (= normalized title 順、 抜粋 100 件)\n\n')
    md.append('| # | native title | 種3 demographic | 種3 genres | 種a en | 種a tags 抜粋 |\n|---|---|---|---|---|---|\n')
    for i, n in enumerate(sorted(common)[:100], 1):
        s3 = shu3_by_norm[n][0]
        sa = shua_norm_to_entries[n][0]
        title = s3['title'][:30]
        demo = s3.get('demographic') or '-'
        genres = ','.join(s3.get('genres') or [])[:30]
        en = (sa.get('title') or {}).get('english') or ''
        tags = ', '.join([t.get('name') for t in (sa.get('tags') or [])][:4])[:50]
        md.append(f'| {i} | {title} | {demo} | {genres} | {en[:30]} | {tags} |\n')
    OUT_MD.write_text(''.join(md), encoding='utf-8')

    print(f'→ {OUT_MD}', flush=True)
    print(f'→ {OUT_TXT} ({len(lines_txt)} lines)', flush=True)
    print(f'→ {OUT_CSV} ({len(lines_csv)} lines)', flush=True)

if __name__ == '__main__':
    main()
