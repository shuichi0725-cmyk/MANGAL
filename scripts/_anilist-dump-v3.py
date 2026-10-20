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
import sys, json, urllib.request, urllib.error, time, gzip, datetime
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
# ★1990年以降は1年ごと(2026-10-20): 上限5,000に当たると100ページ分を捨てて二分し直す(1回~2.5分)。
#   旧の数年まとめは本走で上限に9回当たっていた。 1年で5,000を超える年(2023年前後)だけ月単位に割れる
INITIAL_YEAR_RANGES = (
    [(None, 1970), (1970, 1980), (1980, 1985), (1985, 1990)]
    + [(y, y + 1) for y in range(1990, 2026)]
    + [(2026, None)]    # 2026+(上限は今年+5年)
)
# startDate なし の entry は 別 chunk
NO_DATE_CHUNK = 'no_date'
# ★↑は使われておらず、発売日の範囲で区切る本走では startDate なしの作品が1件も取れない(2026-10-20 実測:
#   旧 dump は delta 合流で33件持っていたが本走は0件)+ 範囲に入るはずの作品も稀に抜ける(勇者パーティーに
#   かわいい子がいたので、告白してみた。2021-01-25)。 → 本走の最後に carry_over() で、前の dump と delta に
#   在って今回取れていない ID を id_in で取り直す(在れば最新の中身で足す・無ければ AniList 側で削除済み)。
DELTA_JSONL = Path('.cache/anilist-delta.jsonl')

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

# ID 指定で取り直す用(本走と同じ field。 削除済みの ID は結果に出ないだけ)
QUERY_IDS = (QUERY
             .replace('query ($page: Int, $format: MediaFormat, $startGT: FuzzyDateInt, $startLT: FuzzyDateInt) {',
                      'query ($ids: [Int]) {', 1)
             .replace('Page(page: $page, perPage: 50)', 'Page(page: 1, perPage: 50)', 1)
             .replace('''media(
      type: MANGA,
      countryOfOrigin: "JP",
      format: $format,
      startDate_greater: $startGT,
      startDate_lesser: $startLT,
      sort: ID
    )''', 'media(id_in: $ids, type: MANGA, sort: ID)', 1))
assert '$ids' in QUERY_IDS and 'startDate_greater' not in QUERY_IDS


def yyyymmdd(year, month=1, day=1):
    return int(f'{year:04d}{month:02d}{day:02d}')

def fetch_page(variables, max_retry=5, query=None):
    data = json.dumps({'query': query or QUERY, 'variables': variables}).encode('utf-8')
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

def _first(m):
    """月の通し番号(年*12+月-1) → その月の1日。"""
    y, mo = divmod(m, 12)
    return datetime.date(y, mo + 1, 1)


def _fz(d):
    return int(f'{d.year:04d}{d.month:02d}{d.day:02d}')


def _mlabel(m):
    y, mo = divmod(m, 12)
    return f'{y}' if mo == 0 else f'{y}-{mo + 1:02d}'


def fetch_chunk(format_str, lo_m, hi_m, seen_ids, chunk_id=None):
    """[lo_m, hi_m) の月範囲(通し番号)を fetch + dedup。 cap (= 5000 hit) なら月単位で二分して再帰。
    ★境目は**実在する日付だけ**を使い、両端を1日ずつ外へ広げて隣と重ねる(重なりは seen_ids で除く):
      startDate_greater = 範囲の初日の前日 / startDate_lesser = 次範囲の初日の翌日。
      → 年だけ(20250000)・月だけ(20250100)・境目の1日 のどれも、どこかの範囲に必ず入る。
    ★実在しない日付(20250099 等)を境目に渡すと AniList はずれた日付として扱い、範囲の前の方が丸ごと落ちる
      (2026-10-20 実測: 2025-01~2030-12 が 2,550件=2025年だけを年キーで取った 4,066件より少ない)。
    ★旧版は年単位でしか割れず、端の開いた区分(~1989 / 2025~)が先頭5,000件で打ち切られていた
      (2026-10-20 実踏: 106,832 → 88,444件。縮小ガードが止めた)。"""
    chunk_id = chunk_id or f'{format_str}_{_mlabel(lo_m)}_{_mlabel(hi_m)}'
    variables = {'format': format_str,
                 'startGT': _fz(_first(lo_m) - datetime.timedelta(days=1)),
                 'startLT': _fz(_first(hi_m) + datetime.timedelta(days=1))}

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
            if hi_m - lo_m > 1:
                mid = (lo_m + hi_m) // 2
                print(f'[{chunk_id}] subdivide → {_mlabel(lo_m)}~{_mlabel(mid)} + {_mlabel(mid)}~{_mlabel(hi_m)}', flush=True)
                # discard partial collection (will re-fetch via subdivision)
                # remove chunk_entries from seen_ids so subdivisions re-collect them
                for e in chunk_entries:
                    seen_ids.discard(e['id'])
                a = fetch_chunk(format_str, lo_m, mid, seen_ids)
                b = fetch_chunk(format_str, mid, hi_m, seen_ids)
                return a + b
            else:
                print(f'[{chunk_id}] WARN: cannot subdivide (1か月で5,000件超), accept first 5000', flush=True)
                break

        page += 1
        time.sleep(1.5)

    print(f'[{chunk_id}] DONE pages={page} entries={len(chunk_entries)}', flush=True)
    return chunk_entries

def _ids_in(path):
    """dump(gzip)/delta(平文) の jsonl から MANGA/ONE_SHOT の id 集合。 拡張子でなく先頭バイトで gzip 判定(.bak-* 名)。"""
    ids = set()
    if not path or not Path(path).exists():
        return ids
    with open(path, 'rb') as fh:
        gz = fh.read(2) == b'\x1f\x8b'
    opener = (lambda: gzip.open(path, 'rt', encoding='utf-8')) if gz else (lambda: open(path, encoding='utf-8'))
    with opener() as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            if m.get('format') in FORMATS and m.get('countryOfOrigin', 'JP') == 'JP':
                ids.add(m['id'])
    return ids


def carry_over(seen_ids, prev_paths):
    """前の dump / delta に在って今回の本走で取れていない ID を id_in で取り直す(50件/req)。"""
    cand = set()
    for p in prev_paths:
        cand |= _ids_in(p)
    cand -= seen_ids
    ids = sorted(cand)
    got = []
    for i in range(0, len(ids), 50):
        pg = fetch_page({'ids': ids[i:i + 50]}, query=QUERY_IDS)
        for m in (pg or {}).get('media') or []:
            if m['id'] in seen_ids or m.get('format') not in FORMATS or m.get('countryOfOrigin') != 'JP':
                continue
            seen_ids.add(m['id'])
            got.append(m)
        time.sleep(1.5)
    nd = sum(1 for m in got if not (m.get('startDate') or {}).get('year'))
    print(f'[carry_over] 前の dump/delta に在り本走に無い {len(ids)} 件 → 取り直し {len(got)}(うち発売日なし {nd})'
          f' / AniList 側で削除・対象外 {len(ids) - len(got)}', flush=True)
    return got


def carry_only(prev):
    """今の dump に carry_over の分だけ足す(本走をやり直さずに直す用)。 --carry-only <前の dump>"""
    import os
    seen = _ids_in(OUT_JSONL)
    extra = carry_over(seen, [Path(prev), DELTA_JSONL])
    if not extra:
        return
    tmp = OUT_JSONL.with_name(OUT_JSONL.name + '.tmp')
    with gzip.open(OUT_JSONL, 'rb') as src, gzip.open(tmp, 'wb') as out:
        for line in src:
            out.write(line)
        for e in extra:
            out.write((json.dumps(e, ensure_ascii=False) + '\n').encode('utf-8'))
    os.replace(tmp, OUT_JSONL)
    print(f'DONE: +{len(extra)} → {OUT_JSONL}', flush=True)


def main():
    if '--carry-only' in sys.argv:
        return carry_only(sys.argv[sys.argv.index('--carry-only') + 1])
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
    # ★本走は一時ファイルに書き、最後に差し替える(取り直し中の約2時間、正規の dump が書きかけになり
    #   promote/他言語名が EOFError で落ちていた 2026-10-20)。 resume は既存に追記するので直接書く
    out_path = OUT_JSONL if resume else OUT_JSONL.with_name(OUT_JSONL.name + '.tmp')
    this_year = time.localtime().tm_year

    with gzip.open(out_path, write_mode) as f:
        for fmt in formats:
            for start_year, end_year in ranges:
                chunk_id = f'{fmt}_{start_year or "PRE"}_{end_year or "POST"}'
                if chunk_id in done_chunks:
                    print(f'[{chunk_id}] SKIP (done)', flush=True)
                    continue
                # 端の開いた区分にも具体的な上下限を与える(=二分できる)。 西暦1000年1月 / 今年+5年1月
                lo_m = (start_year or 1000) * 12
                hi_m = (end_year or this_year + 5) * 12
                try:
                    entries = fetch_chunk(fmt, lo_m, hi_m, seen_ids, chunk_id)
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
        if not test_mode:
            # 前の dump(本走は .tmp に書くので正規パスはまだ前のまま)+ delta の取りこぼしを取り直す
            for e in carry_over(seen_ids, ([] if resume else [OUT_JSONL]) + [DELTA_JSONL]):
                f.write((json.dumps(e, ensure_ascii=False) + '\n').encode('utf-8'))
                total_written += 1

    if out_path != OUT_JSONL:
        import os
        os.replace(out_path, OUT_JSONL)
    elapsed = time.time() - start
    print(f'DONE: {total_written} entries, elapsed={elapsed/60:.1f} min', flush=True)
    print(f'  → {OUT_JSONL} ({OUT_JSONL.stat().st_size / 1024 / 1024:.1f} MB)', flush=True)

if __name__ == '__main__':
    main()
