"""AniList API sample test = 種3 内の 著名作品 を search → English title 取得。

AniList GraphQL:
  endpoint: https://graphql.anilist.co
  rate limit: 90 req/min (= 30 burst sustained 90)
  no API key needed
  license: ToS (= 非商用想定、 commercial OK は要確認)
"""
import sys
import json
import urllib.request
from pathlib import Path
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path('.cache/anilist-test.json')
UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'

QUERY = '''
query ($search: String) {
  Page(perPage: 5) {
    media(search: $search, type: MANGA) {
      id
      title { romaji english native }
      synonyms
      genres
      tags { name rank }
      description
      chapters
      volumes
      status
      format
      countryOfOrigin
      isAdult
    }
  }
}
'''

def search(title: str) -> list:
    data = json.dumps({'query': QUERY, 'variables': {'search': title}}).encode('utf-8')
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={'User-Agent': UA, 'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())['data']['Page']['media']

TEST_TITLES = [
    'ブラック・ジャック',
    '鉄腕アトム',
    '火の鳥',
    'ジャングル大帝',
    'リボンの騎士',
    '進撃の巨人',
    '鬼滅の刃',
    '名探偵コナン',
    'ワンピース',
    '呪術廻戦',
    'スパイファミリー',
    '不滅のあなたへ',
    'ベルセルク',
    'ヴィンランド・サガ',
    '東京リベンジャーズ',
]

def main():
    results = []
    for title in TEST_TITLES:
        print(f'\n=== search: {title} ===')
        try:
            hits = search(title)
            print(f'  {len(hits)} hits')
            for h in hits[:3]:
                t = h.get('title', {})
                romaji = t.get('romaji', '') or ''
                english = t.get('english', '') or ''
                native = t.get('native', '') or ''
                genres = h.get('genres', []) or []
                print(f'  - native={native[:25]:25s} en={english[:30]:30s} romaji={romaji[:20]:20s} genres={genres[:3]}')
            results.append({'query': title, 'hits': hits[:3]})
            time.sleep(1.5)  # 60/min を意識して 1.5sec
        except Exception as e:
            print(f'  ERROR: {e}')
            results.append({'query': title, 'error': str(e)})

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n→ {OUT}')

if __name__ == '__main__':
    main()
