"""直接 候補 query 版 = 種3 iteration せず known 候補だけ AniList に投げる。

10 サンプル得られるまで 続けるのではなく、 候補 全て 試行 → 短縮された entry を 報告。
"""
import sys
import re
import json
import urllib.request
import urllib.error
from pathlib import Path
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path('.cache/anilist-shortened-samples-9.json')
UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'

# 「English: Romaji」 or 「Romaji: English」 pattern が想定される 候補 (= 50 件)
CANDIDATES = [
    # 最終追加
    'かぐや様は告らせたい',
    '黒子のバスケ', '図書館戦争', '蒼穹のファフナー',
    '古見さんは、コミュ症です。', '山田くんと7人の魔女',
    '転生したらスライムだった件', 'バカと試験と召喚獣',
    'カーニヴァル',
    'グレートティーチャーオニヅカ',
    '蒼の彼方のフォーリズム',
    '魔法少女リリカルなのは',
    'ARIA', '東京リベンジャーズ', '陰の実力者になりたくて!',
    '転生したら剣でした', 'なれの果ての僕ら',
    '黎明のアルカナ', '宇宙よりも遠い場所',
    'グランブルーファンタジー',
    '機動戦士ガンダム0083スターダスト・メモリー',
    '無職転生 〜異世界行ったら本気だす〜',
    'スーパーカブ', '銀河鉄道999',
    '進撃!巨人中学校', '亜人',
    '魔法少女リリカルなのは Vivid',
    '神之塔', '名探偵コナン犯人の犯沢さん',
]

QUERY = '''
query ($search: String) {
  Page(perPage: 8) {
    media(search: $search, type: MANGA) {
      title { romaji english native }
      format
      chapters
      volumes
    }
  }
}
'''

MANGA_FORMATS = {'MANGA', 'ONE_SHOT', 'MANHWA', 'MANHUA', 'OEL'}

def normalize(s: str) -> str:
    """alphanumeric only + lowercase + ローマ字表記揺れを 吸収 (= 長音 + 訓令式↔ヘボン式)"""
    s = re.sub(r'[^a-z0-9]', '', (s or '').lower())
    # Long vowels: ou→o, uu→u, oo→o, ee→e, aa→a
    s = re.sub(r'ou', 'o', s)
    s = re.sub(r'uu', 'u', s)
    s = re.sub(r'oo', 'o', s)
    s = re.sub(r'ee', 'e', s)
    s = re.sub(r'aa', 'a', s)
    # ii is sometimes 長音 but often legitimate vowel-vowel, skip
    # Hepburn standardization: ヘボン式 に統一
    s = s.replace('si', 'shi')
    s = s.replace('ti', 'chi')
    s = s.replace('tu', 'tsu')
    s = s.replace('hu', 'fu')
    s = s.replace('zi', 'ji')
    s = s.replace('di', 'ji')
    s = s.replace('du', 'zu')
    return s

def clean_english(english: str, romaji: str) -> str | None:
    if not english or not romaji:
        return None
    n_romaji = normalize(romaji)
    if not n_romaji or len(n_romaji) < 4:
        return None
    for sep in [':', ' - ']:
        if sep in english:
            head, tail = english.split(sep, 1)
            head, tail = head.strip(), tail.strip()
            if not head or not tail:
                continue
            n_head = normalize(head)
            n_tail = normalize(tail)
            # full match: tail == romaji → strip tail
            if n_tail == n_romaji:
                return head
            # full match: head == romaji → strip head
            if n_head == n_romaji:
                return tail
    return None

def best_match(hits, query):
    """format=MANGA系 優先で native 完全一致 → 残り native 一致 → 先頭"""
    n_q = normalize(query)
    # 1st pass: format=MANGA系 + native 完全一致
    for h in hits:
        if h.get('format') not in MANGA_FORMATS:
            continue
        n = normalize(h.get('title', {}).get('native', ''))
        if n == n_q:
            return h
    # 2nd pass: format=MANGA系 のみ
    for h in hits:
        if h.get('format') in MANGA_FORMATS:
            return h
    return None  # MANGA 系 hit なし

def search(title):
    data = json.dumps({'query': QUERY, 'variables': {'search': title}}).encode('utf-8')
    req = urllib.request.Request(
        ENDPOINT, data=data,
        headers={'User-Agent': UA, 'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())['data']['Page']['media']

def main():
    samples = []
    all_results = []
    for i, title in enumerate(CANDIDATES):
        retry = 0
        while True:
            try:
                hits = search(title)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and retry < 5:
                    wait = 10 * (2 ** retry)
                    print(f'  429, retry in {wait}s', flush=True)
                    time.sleep(wait)
                    retry += 1
                    continue
                print(f'  ERROR {title}: {e}', flush=True)
                hits = []
                break
            except Exception as e:
                print(f'  ERROR {title}: {e}', flush=True)
                hits = []
                break

        m = best_match(hits, title)
        if not m:
            print(f'[{i:02d}] {title}: NO HIT')
            all_results.append({'query': title, 'hit': None})
            time.sleep(1.8)
            continue

        en = m.get('title', {}).get('english') or ''
        romaji = m.get('title', {}).get('romaji') or ''
        native = m.get('title', {}).get('native') or ''
        fmt = m.get('format') or ''
        shortened = clean_english(en, romaji)

        marker = ' '
        if shortened and shortened != en:
            marker = '★'
            samples.append({
                'native_in_seed': title,
                'anilist_native': native,
                'anilist_en': en,
                'anilist_romaji': romaji,
                'format': fmt,
                'shortened_en': shortened,
            })
        print(f'[{i:02d}] {marker} {title:25s} [{fmt:8s}] en="{en[:40]:40s}" romaji="{romaji[:25]}" {"→ "+shortened if shortened else ""}', flush=True)
        all_results.append({'query': title, 'en': en, 'romaji': romaji, 'native': native, 'format': fmt, 'shortened': shortened})
        time.sleep(1.8)

    print(f'\n=== summary ===')
    print(f'queried: {len(CANDIDATES)}')
    print(f'samples (shortened): {len(samples)}')

    # 結果出力
    OUT.write_text(json.dumps({
        'samples': samples,
        'all_results': all_results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    if samples:
        print(f'\n=== 短縮サンプル ({len(samples)} 件) ===')
        print(f'{"日本語":35s} | {"AniList en (元)":50s} | 短縮後')
        print('-' * 120)
        for s in samples:
            ja = s['native_in_seed'][:35]
            en = s['anilist_en'][:50]
            sh = s['shortened_en']
            print(f'{ja:35s} | {en:50s} | {sh}')

if __name__ == '__main__':
    main()
