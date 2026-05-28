"""AniList で 種3 を 回して 「English: Romaji」 が clean で短縮されるサンプル 10 件 集める。"""
import sys
import re
import json
import urllib.request
from pathlib import Path
import time
import yaml

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path('.cache/anilist-shortened-samples.json')
UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
ENDPOINT = 'https://graphql.anilist.co'

QUERY = '''
query ($search: String) {
  Page(perPage: 3) {
    media(search: $search, type: MANGA) {
      title { romaji english native }
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

def normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def clean_english(english: str, romaji: str) -> str | None:
    """両方向 shorten:
    "Demon Slayer: Kimetsu no Yaiba" (romaji=Kimetsu no Yaiba) → "Demon Slayer" (tail==romaji)
    "Kimi ni Todoke: From Me to You" (romaji=Kimi ni Todoke) → "From Me to You" (head==romaji)
    "Sword Art Online: Phantom Bullet" (romaji=Sword Art Online Phantom Bullet) → keep
    """
    if not english or not romaji:
        return None
    n_romaji = normalize(romaji)
    if not n_romaji:
        return None
    for sep in [':', ' - ']:
        if sep in english:
            head, tail = english.split(sep, 1)
            head, tail = head.strip(), tail.strip()
            if not head or not tail:
                continue
            n_head = normalize(head)
            n_tail = normalize(tail)
            # tail == romaji → strip tail (= "Demon Slayer: Kimetsu no Yaiba")
            if n_tail == n_romaji and len(n_tail) >= 6:
                return head
            # head == romaji → strip head (= "Kimi ni Todoke: From Me to You")
            if n_head == n_romaji and len(n_head) >= 6:
                return tail
    return None

def best_match(hits: list, query: str) -> dict | None:
    """native 完全一致を優先。"""
    if not hits:
        return None
    n_q = normalize(query)
    for h in hits:
        n = normalize(h.get('title', {}).get('native', ''))
        if n == n_q:
            return h
    return hits[0]

KANJI_RE = re.compile(r'[一-鿿]')

# 「English: Romaji」 pattern が AniList で 発生しそうな known 候補 (= 優先 query)
PRIORITY_CANDIDATES = [
    '鬼滅の刃', '食戟のソーマ', '君に届け', '暁のヨナ', 'ふしぎ遊戯',
    '銀の匙', '海月姫', 'PLUTO', '蒼天航路', '宇宙兄弟',
    '青の祓魔師', '青の魔導師', '青の祓魔師-青のミブロ-', 'のだめカンタービレ', '魔法陣グルグル',
    '夏目友人帳', '神様はじめました', '黒執事', '幽☆遊☆白書', '南国少年パプワくん',
    '銀河鉄道999', '鋼の錬金術師', '結界師', '蟲師', 'らんま1/2',
    '蒼天の拳', '彼岸島', 'ピンポン', '聖闘士星矢', '東京喰種',
    '魔女と野獣', '不機嫌なモノノケ庵', '武装錬金', '魔人探偵脳噛ネウロ', 'シャーマンキング',
    '美味しんぼ', '寄生獣', '帝一の國', '謎の彼女X', '銀魂',
    '黒子のバスケ', 'ハイキュー!!', 'ジョジョの奇妙な冒険', '進撃の巨人', '魔法少女まどか☆マギカ',
    '化物語', '伝説の勇者の伝説', '王立宇宙軍', 'タッチ', '名探偵コナン',
]

def main():
    print('loading 種3...')
    with open('data/seeds/series-supplement-v2.yml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    series = data['series']
    # native title 抽出 + 重複除外
    seen_titles = set()
    queries_kanji = []  # kanji 含む = 「Engish: Romaji」 patterns 出やすい
    queries_other = []
    for entry in series:
        key = entry.get('key', '')
        parts = key.split('|')
        title_parts = [p[5:] for p in parts if p.startswith('name:')]
        if len(title_parts) < 2:
            continue
        title = title_parts[-1]
        if title in seen_titles:
            continue
        seen_titles.add(title)
        if len(title) < 3:
            continue
        if '|sub:' in key:
            continue
        # kanji 含む を 優先キュー へ
        if KANJI_RE.search(title):
            queries_kanji.append((title, entry))
        else:
            queries_other.append((title, entry))
    # PRIORITY 候補 を 先頭に
    title_to_entry = {t: e for t, e in queries_kanji + queries_other}
    priority_queue = [(t, title_to_entry[t]) for t in PRIORITY_CANDIDATES if t in title_to_entry]
    priority_set = set(t for t, _ in priority_queue)
    rest = [(t, e) for t, e in queries_kanji + queries_other if t not in priority_set]
    queries = priority_queue + rest
    print(f'priority candidates matched: {len(priority_queue)}/{len(PRIORITY_CANDIDATES)}')
    print(f'unique queries total: {len(queries):,}')

    samples = []
    queried = 0
    hit_with_en = 0
    consecutive_429 = 0
    print('\n=== iteration start ===', flush=True)
    for i, (title, entry) in enumerate(queries):
        if len(samples) >= 10:
            break
        try:
            hits = search(title)
            queried += 1
            consecutive_429 = 0
        except urllib.error.HTTPError as e:
            if e.code == 429:
                consecutive_429 += 1
                backoff = min(60, 5 * (2 ** consecutive_429))
                print(f'  [{i}] 429 (consecutive {consecutive_429}) → sleep {backoff}s', flush=True)
                time.sleep(backoff)
                continue
            print(f'  [{i}] ERROR {title}: {e}', flush=True)
            time.sleep(3)
            continue
        except Exception as e:
            print(f'  [{i}] ERROR {title}: {e}', flush=True)
            time.sleep(3)
            continue

        m = best_match(hits, title)
        if not m:
            time.sleep(1.8)
            continue
        en = m.get('title', {}).get('english') or ''
        romaji = m.get('title', {}).get('romaji') or ''
        if not en:
            time.sleep(1.8)
            continue
        hit_with_en += 1

        shortened = clean_english(en, romaji)
        if shortened and shortened != en:
            samples.append({
                'native_in_seed': title,
                'anilist_native': m['title'].get('native'),
                'anilist_en': en,
                'anilist_romaji': romaji,
                'shortened_en': shortened,
            })
            print(f'  [{i}] ★ #{len(samples)}: {title} → en="{en}" → 短縮="{shortened}"', flush=True)
        else:
            if i % 30 == 0:
                print(f'  [{i}] (n={len(samples)}) {title[:25]:25s} en="{en[:40]}"', flush=True)

        time.sleep(1.8)  # rate limit 配慮 (= ~33 req/min、 安全マージン)

    print(f'\n=== summary ===')
    print(f'queried: {queried}')
    print(f'hit_with_en: {hit_with_en}')
    print(f'samples (shortened): {len(samples)}')

    OUT.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n→ {OUT}')

    # 表示
    print('\n=== 短縮サンプル一覧 ===')
    print(f'{"日本語":35s} | {"AniList en (元)":50s} | 短縮後')
    print('-' * 120)
    for s in samples:
        ja = s['native_in_seed'][:35]
        en = s['anilist_en'][:50]
        sh = s['shortened_en']
        print(f'{ja:35s} | {en:50s} | {sh}')

if __name__ == '__main__':
    main()
