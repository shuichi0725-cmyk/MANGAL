"""Wikipedia 記事冒頭の よみがな 取得 試験 (= MediaWiki API)。

日本語 Wikipedia 記事は 「作品名(よみがな)」 と 冒頭に書く。
記事 extract から 括弧内よみがな を 抽出できるか サンプルで検証。
"""
import sys, json, re, urllib.parse, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'

def get_extract(title):
    params = urllib.parse.urlencode({
        'action': 'query', 'prop': 'extracts', 'exintro': 1, 'explaintext': 1,
        'titles': title, 'redirects': 1, 'format': 'json',
    })
    url = f'https://ja.wikipedia.org/w/api.php?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    pages = d.get('query', {}).get('pages', {})
    for pid, p in pages.items():
        if pid == '-1':  # 記事なし
            return None, p.get('title', title)
        return p.get('extract', ''), p.get('title', title)
    return None, title

def parse_yomi(extract):
    """冒頭の 「（よみがな）」 を 抽出 (= ひらがな/カタカナ主体)"""
    if not extract: return None
    head = extract[:300]
    # 全角/半角括弧、 よみは かな + 中黒/長音/スペース
    for m in re.finditer(r'[（(]([ぁ-んァ-ヶーｰ・,、\s]+)[）)]', head):
        cand = m.group(1).strip()
        kana = sum(1 for c in cand if 'ぁ' <= c <= 'ん' or 'ァ' <= c <= 'ヶ')
        if kana >= 3:  # かな3字以上 = よみがな らしい
            return cand
    return None

def main():
    samples = ['GS美神 極楽大作戦', '神統記', '観用少女', 'BANANA FISH',
               '鋼の錬金術師', '吸血姫美夕', '水中騎士']
    print('=== Wikipedia 記事冒頭よみがな 試験 ===')
    for t in samples:
        try:
            extract, resolved = get_extract(t)
            if extract is None:
                print(f'  {t!r}: 記事なし')
            else:
                yomi = parse_yomi(extract)
                print(f'  {t!r} (→記事 {resolved!r})')
                print(f'    よみ抽出: {yomi!r}')
                print(f'    冒頭: {extract[:80]!r}')
            time.sleep(0.4)
        except Exception as e:
            print(f'  {t!r}: ERROR {e}')

if __name__ == '__main__':
    main()
