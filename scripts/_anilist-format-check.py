"""短縮サンプル 11 件 の AniList format を 検証。
format=NOVEL は light novel = MANGAL 対象外。
"""
import sys, json, urllib.request, urllib.error, time, re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'

QUERY = '''
query ($search: String) {
  Page(perPage: 5) {
    media(search: $search, type: MANGA) {
      title { romaji english native }
      format
      chapters
      volumes
      status
    }
  }
}
'''

TARGETS = [
    '鬼滅の刃', '化物語', '偽物語', '傷物語', '終物語',
    '憑物語', '君に届け', '暦物語', '続・終物語', '鬼物語', '囮物語',
]

def normalize(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def search(title):
    data = json.dumps({'query': QUERY, 'variables': {'search': title}}).encode('utf-8')
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={'User-Agent': UA, 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())['data']['Page']['media']

def main():
    print(f'{"日本語":15s} | {"format":10s} | {"vols":4s} | {"chaps":5s} | {"en"}')
    print('-' * 100)
    for t in TARGETS:
        try:
            hits = search(t)
            time.sleep(1.8)
        except Exception as e:
            print(f'{t}: ERROR {e}')
            continue
        # best match
        n_q = normalize(t)
        best = None
        for h in hits:
            if normalize(h.get('title', {}).get('native', '')) == n_q:
                best = h
                break
        if not best and hits:
            best = hits[0]
        if not best:
            print(f'{t:15s} | NO HIT')
            continue
        fmt = best.get('format') or '-'
        vols = best.get('volumes')
        chaps = best.get('chapters')
        en = best.get('title', {}).get('english') or ''
        vols_s = str(vols) if vols else '-'
        chaps_s = str(chaps) if chaps else '-'
        mark = '⚠' if fmt == 'NOVEL' else '✓'
        print(f'{mark} {t:13s} | {fmt:10s} | {vols_s:4s} | {chaps_s:5s} | {en}')

if __name__ == '__main__':
    main()
