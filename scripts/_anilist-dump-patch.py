"""AniList dump patch = 2021-2024 単年 × 双方向 sort で 欠損補完。

戦略:
  既存 dump (= .cache/anilist-manga-dump.jsonl.gz) から id を読み込み
  対象 年 × format を ASC + DESC で各 5000 件 まで取得
  新規 id のみ 既存 dump に append

対象:
  MANGA + ONE_SHOT
  2021, 2022, 2023, 2024 (= 各単年)

各 (year, format) で:
  ASC fetch (= page 1-100 で 古い ID 5000 件)
  DESC fetch (= page 1-100 で 新しい ID 5000 件)
  → 単年 10,000 件 までカバー (= 重複は dedup)
"""
import sys, json, urllib.request, urllib.error, time, gzip
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'
DUMP = Path('.cache/anilist-manga-dump.jsonl.gz')

QUERY = '''
query ($page: Int, $format: MediaFormat, $startGT: FuzzyDateInt, $startLT: FuzzyDateInt, $sort: [MediaSort]) {
  Page(page: $page, perPage: 50) {
    pageInfo { total currentPage lastPage hasNextPage }
    media(
      type: MANGA, countryOfOrigin: "JP", format: $format,
      startDate_greater: $startGT, startDate_lesser: $startLT, sort: $sort
    ) {
      id idMal
      title { romaji english native }
      synonyms type format status source(version: 3)
      countryOfOrigin isAdult volumes
      startDate { year month day }
      endDate { year month day }
      genres
      tags { name rank category isGeneralSpoiler isMediaSpoiler isAdult }
      relations { edges { relationType node { id type format title { romaji english native } } } }
      staff(perPage: 10) { edges { role node { id name { full native } } } }
    }
  }
}
'''

def fetch_page(variables, max_retry=5):
    data = json.dumps({'query': QUERY, 'variables': variables}).encode('utf-8')
    for retry in range(max_retry):
        try:
            req = urllib.request.Request(ENDPOINT, data=data,
                headers={'User-Agent': UA, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())['data']['Page']
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                wait = 5 * (2 ** retry)
                print(f'  HTTP {e.code}, sleep {wait}s', flush=True)
                time.sleep(wait)
                continue
            if e.code == 400:
                body = e.read().decode('utf-8')
                print(f'  HTTP 400: {body[:200]}', flush=True)
                return None
            raise
        except Exception as e:
            wait = 5 * (retry + 1)
            print(f'  error: {e}, sleep {wait}s', flush=True)
            time.sleep(wait)
            continue
    return None

def fetch_year_sort(format_str, year, sort_dir):
    """sort_dir = 'ID' (= ASC) or 'ID_DESC'"""
    start_gt = year * 10000 + 101
    start_lt = (year + 1) * 10000 + 101
    label = f'{format_str}_{year}_{sort_dir}'
    entries = []
    page = 1
    while True:
        variables = {
            'page': page, 'format': format_str,
            'startGT': start_gt, 'startLT': start_lt,
            'sort': [sort_dir],
        }
        p = fetch_page(variables)
        if p is None:
            print(f'[{label}] page {page} returned None, abort', flush=True)
            break
        media = p.get('media') or []
        for m in media:
            entries.append(m)
        info = p.get('pageInfo') or {}
        if page == 1:
            print(f'[{label}] total≦{info.get("total")}, lastPage={info.get("lastPage")}', flush=True)
        if not info.get('hasNextPage'):
            break
        if page >= 100:
            print(f'[{label}] hit cap page=100', flush=True)
            break
        page += 1
        time.sleep(1.5)
    print(f'[{label}] DONE pages={page} fetched={len(entries)}', flush=True)
    return entries

def main():
    # 既存 dump 読み込み (= seen_ids)
    print('loading existing dump...', flush=True)
    seen_ids = set()
    if DUMP.exists():
        with gzip.open(DUMP, 'rb') as f:
            for line in f:
                try:
                    e = json.loads(line)
                    seen_ids.add(e['id'])
                except Exception:
                    pass
    print(f'  existing entries: {len(seen_ids):,}', flush=True)

    new_added = 0
    start = time.time()
    YEARS = [2021, 2022, 2023, 2024]
    FORMATS = ['MANGA', 'ONE_SHOT']

    with gzip.open(DUMP, 'ab') as f:
        for fmt in FORMATS:
            for year in YEARS:
                for sort_dir in ['ID', 'ID_DESC']:
                    entries = fetch_year_sort(fmt, year, sort_dir)
                    added_this = 0
                    for m in entries:
                        mid = m['id']
                        if mid in seen_ids:
                            continue
                        seen_ids.add(mid)
                        f.write((json.dumps(m, ensure_ascii=False) + '\n').encode('utf-8'))
                        new_added += 1
                        added_this += 1
                    print(f'  → 新規追加 {added_this}/+{new_added} total dump={len(seen_ids):,}', flush=True)

    elapsed = time.time() - start
    print(f'PATCH DONE: +{new_added} entries (= total now {len(seen_ids):,}), elapsed={elapsed/60:.1f}min', flush=True)
    print(f'  → {DUMP} ({DUMP.stat().st_size / 1024 / 1024:.1f} MB)', flush=True)

if __name__ == '__main__':
    main()
