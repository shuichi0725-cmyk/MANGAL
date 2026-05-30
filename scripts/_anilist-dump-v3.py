"""AniList JP manga bulk dump v2 = 年代+format 細分化。

戦略:
  API は (page 100, perPage 50) = max 5,000 entries の hard cap。
  → (年代範囲, format) で 細分化 して chunk ごとに dump。
  → cap 当たったら さらに 年範囲 半分割で 再帰。

取得 field (= 19 項目 確定):
  必須: id, title.native, title.romaji, title.english, type, format,
        status, countryOfOrigin, isAdult, startDate, endDate, volumes, genres, tags
  推奨: idMal, synonyms, source, relations, staff

出力:
  .cache/anilist-manga-dump.jsonl.gz  (= 1 行 1 entry、 dedup 済)
  .cache/anilist-dump-progress.json   (= chunk 進捗、 resume 用)

CLI:
  python _anilist-dump-v2.py            # 本走
  python _anilist-dump-v2.py --test     # 2 chunk のみ test
  python _anilist-dump-v2.py --resume   # 中断時 続き
"""
import sys, json, urllib.request, urllib.error, time, gzip
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'
OUT_JSONL = Path('.cache/anilist-manga-dump-v3.jsonl.gz')
PROGRESS = Path('.cache/anilist-dump-v3-progress.json')

# 初期 chunk 計画 (= 年代範囲)。 各 chunk 5000 未満を 期待
# (start_inclusive, end_exclusive) の YYYY 形式、 None = 上限/下限 なし
INITIAL_YEAR_RANGES = [
    (None, 1990),    # ~1989
    (1990, 1995),
    (1995, 2000),
    (2000, 2005),
    (2005, 2010),
    (2010, 2013),
    (2013, 2015),
    (2015, 2017),
    (2017, 2019),
    (2019, 2021),
    (2021, 2023),
    (2023, 2025),
    (2025, None),    # 2025+
]
# startDate なし の entry は 別 chunk
NO_DATE_CHUNK = 'no_date'

FORMATS = ['MANGA', 'ONE_SHOT']  # NOVEL は除外 (= LN 不要)

QUERY = '''
query ($page: Int, $format: MediaFormat, $startGT: FuzzyDateInt, $startLT: FuzzyDateInt) {
  Page(page: $page, perPage: 50) {
    pageInfo { total currentPage lastPage hasNextPage }
    media(
      type: MANGA,
      countryOfOrigin: "JP",
      format: $format,
      startDate_greater: $startGT,
      startDate_lesser: $startLT,
      sort: ID
    ) {
      id
      idMal
      title { romaji english native }
      synonyms
      type
      format
      status
      source(version: 3)
      countryOfOrigin
      isAdult
      isLicensed
      volumes
      chapters
      startDate { year month day }
      endDate { year month day }
      description(asHtml: false)
      averageScore
      meanScore
      popularity
      favourites
      genres
      tags { name rank category isGeneralSpoiler isMediaSpoiler isAdult }
      relations {
        edges {
          relationType
          node {
            id type format
            title { romaji english native }
          }
        }
      }
      staff(perPage: 10) {
        edges {
          role
          node { id name { full native } }
        }
      }
    }
  }
}
'''

# startDate なし の entry 取得用 (= 年範囲 filter なし、 但し sort で 取り出すか)
# AniList で startDate_lesser を 99999999 にすると 全 entry になるが startDate なしも含む?
# 別 query で 取得

QUERY_NO_DATE = '''
query ($page: Int, $format: MediaFormat) {
  Page(page: $page, perPage: 50) {
    pageInfo { total currentPage lastPage hasNextPage }
    media(
      type: MANGA,
      countryOfOrigin: "JP",
      format: $format,
      sort: ID
    ) {
      id
    }
  }
}
'''

def yyyymmdd(year, month=1, day=1):
    return int(f'{year:04d}{month:02d}{day:02d}')

def fetch_page(variables, max_retry=5):
    data = json.dumps({'query': QUERY, 'variables': variables}).encode('utf-8')
    for retry in range(max_retry):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=data,
                headers={'User-Agent': UA, 'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())['data']['Page']
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                wait = 5 * (2 ** retry)
                print(f'  HTTP {e.code}, sleep {wait}s', flush=True)
                time.sleep(wait)
                continue
            if e.code == 400:
                # Bad request (= page > 100 or similar)
                body = e.read().decode('utf-8')
                print(f'  HTTP 400: {body[:200]}', flush=True)
                return None
            raise
        except Exception as e:
            wait = 5 * (retry + 1)
            print(f'  error: {e}, sleep {wait}s', flush=True)
            time.sleep(wait)
            continue
    raise RuntimeError(f'page fetch failed after {max_retry} retries')

def fetch_chunk(format_str, start_year, end_year, seen_ids):
    """1 chunk を fetch + dedup。 cap (= 5000 hit) なら subdivide 再帰。"""
    start_gt = yyyymmdd(start_year) if start_year else None
    start_lt = yyyymmdd(end_year) if end_year else None
    chunk_id = f'{format_str}_{start_year or "PRE"}_{end_year or "POST"}'

    variables = {'format': format_str}
    if start_gt:
        variables['startGT'] = start_gt
    if start_lt:
        variables['startLT'] = start_lt

    page = 1
    chunk_entries = []
    while True:
        variables['page'] = page
        try:
            p = fetch_page(variables)
        except Exception as e:
            print(f'[{chunk_id}] FATAL page {page}: {e}', flush=True)
            raise
        if p is None:
            # 400 hit (= page > 100 or similar)
            break

        media = p.get('media') or []
        for m in media:
            mid = m['id']
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            chunk_entries.append(m)

        info = p.get('pageInfo') or {}
        last_page = info.get('lastPage') or 0
        has_next = info.get('hasNextPage', False)
        total = info.get('total', 0)

        if page == 1:
            print(f'[{chunk_id}] total≦{total}, lastPage={last_page}', flush=True)

        if not has_next:
            break
        if page >= 100:
            # cap hit, need subdivide
            print(f'[{chunk_id}] hit page=100 cap, need subdivide', flush=True)
            if start_year and end_year and end_year - start_year > 1:
                mid_year = (start_year + end_year) // 2
                # subdivide
                print(f'[{chunk_id}] subdivide → {start_year}-{mid_year} + {mid_year}-{end_year}', flush=True)
                # discard partial collection (will re-fetch via subdivision)
                # remove chunk_entries from seen_ids so subdivisions re-collect them
                for e in chunk_entries:
                    seen_ids.discard(e['id'])
                a = fetch_chunk(format_str, start_year, mid_year, seen_ids)
                b = fetch_chunk(format_str, mid_year, end_year, seen_ids)
                return a + b
            else:
                print(f'[{chunk_id}] WARN: cannot subdivide year=1, accept first 5000', flush=True)
                break

        page += 1
        time.sleep(1.5)

    print(f'[{chunk_id}] DONE pages={page} entries={len(chunk_entries)}', flush=True)
    return chunk_entries

def main():
    test_mode = '--test' in sys.argv
    resume = '--resume' in sys.argv

    if test_mode:
        ranges = [(2024, 2025), (2025, None)]  # 2 chunk のみ
        formats = ['MANGA']
        print('[TEST MODE]')
    else:
        ranges = INITIAL_YEAR_RANGES
        formats = FORMATS

    # progress (= resume 用)
    done_chunks = set()
    if resume and PROGRESS.exists():
        try:
            prog = json.loads(PROGRESS.read_text())
            done_chunks = set(prog.get('done_chunks', []))
            print(f'resume: skip {len(done_chunks)} done chunks', flush=True)
        except Exception:
            pass

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    seen_ids = set()
    # 既存 dump を読み込み (= resume の seen_ids 復元)
    if resume and OUT_JSONL.exists():
        print('loading existing dump for dedup...', flush=True)
        with gzip.open(OUT_JSONL, 'rb') as f:
            for line in f:
                try:
                    e = json.loads(line)
                    seen_ids.add(e['id'])
                except Exception:
                    pass
        print(f'  loaded {len(seen_ids)} existing ids', flush=True)

    write_mode = 'ab' if resume else 'wb'
    total_written = len(seen_ids)
    start = time.time()

    with gzip.open(OUT_JSONL, write_mode) as f:
        for fmt in formats:
            for start_year, end_year in ranges:
                chunk_id = f'{fmt}_{start_year or "PRE"}_{end_year or "POST"}'
                if chunk_id in done_chunks:
                    print(f'[{chunk_id}] SKIP (done)', flush=True)
                    continue
                try:
                    entries = fetch_chunk(fmt, start_year, end_year, seen_ids)
                except Exception as e:
                    print(f'[{chunk_id}] FAIL: {e}', flush=True)
                    PROGRESS.write_text(json.dumps({'done_chunks': sorted(done_chunks)}))
                    raise
                for e in entries:
                    f.write((json.dumps(e, ensure_ascii=False) + '\n').encode('utf-8'))
                    total_written += 1
                done_chunks.add(chunk_id)
                PROGRESS.write_text(json.dumps({'done_chunks': sorted(done_chunks), 'total_written': total_written}))
                elapsed = time.time() - start
                print(f'  → total_written={total_written} elapsed={elapsed/60:.1f}min', flush=True)

    elapsed = time.time() - start
    print(f'DONE: {total_written} entries, elapsed={elapsed/60:.1f} min', flush=True)
    print(f'  → {OUT_JSONL} ({OUT_JSONL.stat().st_size / 1024 / 1024:.1f} MB)', flush=True)

if __name__ == '__main__':
    main()
