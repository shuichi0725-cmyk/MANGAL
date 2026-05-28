"""AniList 全 日本漫画 bulk dump.

取得対象:
  type=MANGA, countryOfOrigin=JP
  ※ format=NOVEL を含む (= client-side filter で 後で除外)

取得 field (= 19 項目、 ユーザ確定済):
  必須 (14): id, title.native, title.romaji, title.english,
             type, format, status, countryOfOrigin,
             isAdult, startDate, endDate, volumes, genres, tags
  推奨 (5):  idMal, synonyms, source, relations, staff

出力:
  .cache/anilist-manga-dump.jsonl.gz  (= 1 行 1 entry の jsonl + gzip)

resume 対応:
  .cache/anilist-dump-state.json で page 番号保存
  中断時に再起動可能

CLI:
  python _anilist-dump.py            # 本走
  python _anilist-dump.py --test     # 5 page test
"""
import sys, json, urllib.request, urllib.error, time, gzip, os
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'
OUT_JSONL = Path('.cache/anilist-manga-dump.jsonl.gz')
STATE = Path('.cache/anilist-dump-state.json')

QUERY = '''
query ($page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo {
      total currentPage lastPage hasNextPage
    }
    media(type: MANGA, countryOfOrigin: "JP", sort: ID) {
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
      volumes
      startDate { year month day }
      endDate { year month day }
      genres
      tags {
        name rank category
        isGeneralSpoiler isMediaSpoiler isAdult
      }
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
          node {
            id
            name { full native }
          }
        }
      }
    }
  }
}
'''

def fetch_page(page: int, max_retry: int = 5):
    data = json.dumps({'query': QUERY, 'variables': {'page': page}}).encode('utf-8')
    for retry in range(max_retry):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=data,
                headers={'User-Agent': UA, 'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())['data']['Page']
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                wait = 5 * (2 ** retry)
                print(f'  page {page} HTTP {e.code}, sleep {wait}s', flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            wait = 5 * (retry + 1)
            print(f'  page {page} error: {e}, sleep {wait}s', flush=True)
            time.sleep(wait)
            continue
    raise RuntimeError(f'page {page} failed after {max_retry} retries')

def main():
    test_mode = '--test' in sys.argv
    max_pages = 5 if test_mode else None

    if test_mode:
        print('[TEST MODE] 5 pages のみ')
        # test mode は 別 file に
        global OUT_JSONL, STATE
        OUT_JSONL = Path('.cache/anilist-manga-dump-test.jsonl.gz')
        STATE = Path('.cache/anilist-dump-state-test.json')

    # resume
    start_page = 1
    if STATE.exists() and not test_mode:
        try:
            st = json.loads(STATE.read_text())
            if not st.get('completed'):
                start_page = st.get('next_page', 1)
                print(f'resume from page {start_page}', flush=True)
        except Exception:
            pass

    page = start_page
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    mode = 'ab' if start_page > 1 else 'wb'
    total_written = 0
    last_emit = time.time()

    with gzip.open(OUT_JSONL, mode) as f:
        while True:
            if max_pages and page > start_page + max_pages - 1:
                print(f'[test] reached max_pages={max_pages}, stop', flush=True)
                break
            try:
                p = fetch_page(page)
            except Exception as e:
                print(f'FATAL page {page}: {e}', flush=True)
                STATE.write_text(json.dumps({'next_page': page}))
                raise

            media_list = p.get('media') or []
            for m in media_list:
                f.write((json.dumps(m, ensure_ascii=False) + '\n').encode('utf-8'))
                total_written += 1

            info = p.get('pageInfo') or {}
            last_page = info.get('lastPage', '?')
            total = info.get('total', '?')

            now = time.time()
            if now - last_emit > 20 or page % 25 == 0 or test_mode:
                print(f'page {page}/{last_page} (total={total}) +{len(media_list)}  total_written={total_written}', flush=True)
                last_emit = now

            if page % 50 == 0 and not test_mode:
                STATE.write_text(json.dumps({'next_page': page + 1, 'total_written': total_written}))

            if not info.get('hasNextPage'):
                print(f'completed at page {page} (= last page)', flush=True)
                break

            page += 1
            time.sleep(1.5)

    if not test_mode:
        STATE.write_text(json.dumps({
            'completed': True, 'last_page': page, 'total_entries': total_written,
        }))
    print(f'DONE: {total_written} entries from {page - start_page + 1} pages', flush=True)
    print(f'  → {OUT_JSONL} (size: {OUT_JSONL.stat().st_size / 1024 / 1024:.1f} MB)', flush=True)

if __name__ == '__main__':
    main()
