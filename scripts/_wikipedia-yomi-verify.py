"""当て字崩れ候補 479件を Wikipedia で 最終確定 (= 4ソース突合)。

入力: .cache/ateji-autojudge.csv (= 種3崩れ候補)
処理: 各 title の Wikipedia 記事冒頭よみがな を取得 → 種3 / 種a推奨 と突合
判定:
  - Wiki = 種3      → 種3正しい (= 種a/MADB の誤判定)
  - Wiki = 種a推奨  → 種3崩れ確定 (= 推奨に直すべき)
  - Wiki = どちらも違う → 第3の読み (要確認)
  - 記事なし / 非漫画記事 → 判定保留
"""
import sys, csv, re, json, urllib.parse, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'

def get_extract(title):
    params = urllib.parse.urlencode({
        'action': 'query', 'prop': 'extracts', 'exintro': 1, 'explaintext': 1,
        'titles': title, 'redirects': 1, 'format': 'json',
    })
    req = urllib.request.Request(f'https://ja.wikipedia.org/w/api.php?{params}',
        headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    for pid, p in d.get('query', {}).get('pages', {}).items():
        if pid == '-1': return None
        return p.get('extract', '')
    return None

def parse_yomi(extract):
    if not extract: return None
    head = extract[:300]
    m = re.search(r'[（(]([^（）()]+)[）)]', head)  # タイトル直後の最初の括弧
    if not m: return None
    inner = m.group(1)
    for part in re.split(r'[、,，:：;；/]', inner):
        part = part.strip()
        body = re.sub(r'[\s　ー・]', '', part)
        if not body: continue
        kana = sum(1 for c in body if 'ぁ' <= c <= 'ん' or 'ァ' <= c <= 'ヶ')
        if kana >= max(2, len(body) * 0.6):  # かな主体
            return part
    return None

def norm(s):
    if not s: return ''
    s = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)  # ひら→カタ
    return re.sub(r'[\s　・ー]', '', s).lower()

def main():
    rows = list(csv.DictReader(open('.cache/ateji-autojudge.csv', encoding='utf-8-sig')))
    print(f'対象: {len(rows):,} 件 を Wikipedia 確認...', flush=True)
    out = []
    stats = {'種3正': 0, '種a正(崩れ確定)': 0, '第3の読み': 0, '記事なし': 0, '非漫画': 0, 'よみ無': 0}
    for i, r in enumerate(rows):
        title = r['title']
        s3 = r['種3現フリガナ']; rec = r['推奨読み(公式)']
        try:
            ext = get_extract(title)
        except Exception:
            ext = None
        verdict = ''; wiki_yomi = ''
        if ext is None:
            verdict = '記事なし'; stats['記事なし'] += 1
        elif ('漫画' not in ext and 'マンガ' not in ext and 'コミック' not in ext):
            verdict = '非漫画(別作品?)'; stats['非漫画'] += 1
        else:
            wiki_yomi = parse_yomi(ext) or ''
            if not wiki_yomi:
                verdict = 'よみ抽出不可'; stats['よみ無'] += 1
            else:
                nw = norm(wiki_yomi)
                if nw == norm(s3):
                    verdict = '種3正しい'; stats['種3正'] += 1
                elif nw == norm(rec):
                    verdict = '種a正(崩れ確定)'; stats['種a正(崩れ確定)'] += 1
                else:
                    verdict = '第3の読み'; stats['第3の読み'] += 1
        out.append({'判定': verdict, 'title': title, '種3現': s3,
                    '種a推奨': rec, 'Wikipediaよみ': wiki_yomi})
        time.sleep(0.35)
        if (i+1) % 50 == 0:
            print(f'  {i+1}/{len(rows)} 処理...', flush=True)

    OUT = '.cache/wikipedia-yomi-verify.csv'
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['判定', 'title', '種3現', '種a推奨', 'Wikipediaよみ'])
        w.writeheader(); w.writerows(out)

    print()
    print('=== Wikipedia 4ソース突合 結果 ===')
    for k, v in stats.items():
        print(f'  {k}: {v:,}')
    print(f'  CSV: {OUT}')
    print()
    print('=== 種a正(崩れ確定) sample = 種3を直すべき ===')
    c = 0
    for o in out:
        if o['判定'] == '種a正(崩れ確定)' and c < 15:
            print(f'  {o["title"]!r}: 種3={o["種3現"]!r} → Wiki確定={o["Wikipediaよみ"]!r}')
            c += 1
    print()
    print('=== 種3正しい sample = 種a誤判定だった ===')
    c = 0
    for o in out:
        if o['判定'] == '種3正しい' and c < 10:
            print(f'  {o["title"]!r}: 種3={o["種3現"]!r} (Wiki一致、 種a推奨={o["種a推奨"]!r}は誤り)')
            c += 1

if __name__ == '__main__':
    main()
