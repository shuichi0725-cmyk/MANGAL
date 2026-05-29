"""16,354件 を Wikipedia で 一括裁定 (= 長時間バッチ、 逐次保存)。

入力: .cache/furigana-wiki-targets.csv (tier/title/種3フリガナ/MADB読み/種a)
出力: .cache/furigana-wiki-result.csv (逐次書き込み、 途中落ちても部分保存)
判定: Wikipedia記事冒頭よみがな を 種3 / MADB読み と突合
  種3正しい / MADB一致(種3崩れ) / 第3の読み / 記事なし / 非漫画 / よみ無
"""
import sys, csv, re, json, urllib.parse, urllib.request, time
sys.stdout.reconfigure(encoding='utf-8')

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
IN = '.cache/furigana-wiki-targets.csv'
OUT = '.cache/furigana-wiki-result.csv'

def get_extract(title):
    params = urllib.parse.urlencode({'action':'query','prop':'extracts','exintro':1,
        'explaintext':1,'titles':title,'redirects':1,'format':'json'})
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
    m = re.search(r'[（(]([^（）()]+)[）)]', extract[:300])
    if not m: return None
    for part in re.split(r'[、,，:：;；/]', m.group(1)):
        part = part.strip()
        body = re.sub(r'[\s　ー・]', '', part)
        if not body: continue
        kana = sum(1 for c in body if 'ぁ' <= c <= 'ん' or 'ァ' <= c <= 'ヶ')
        if kana >= max(2, len(body) * 0.6):
            return part
    return None

def norm(s):
    if not s: return ''
    s = ''.join(chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)
    return re.sub(r'[\s　・ー]', '', s).lower()

def main():
    rows = list(csv.DictReader(open(IN, encoding='utf-8-sig')))
    n = len(rows)
    print(f'Wikipedia 一括裁定: {n:,} 件 開始', flush=True)
    stats = {}
    fo = open(OUT, 'w', encoding='utf-8-sig', newline='')
    w = csv.DictWriter(fo, fieldnames=['判定','tier','title','種3現','MADB読み','Wikipediaよみ','種a'])
    w.writeheader()
    for i, r in enumerate(rows):
        title = r['title']; s3 = r['種3フリガナ']; madb = r['MADB読み']; sa = r.get('種a','')
        try:
            ext = get_extract(title)
        except Exception:
            ext = None
        verdict = ''; wy = ''
        if ext is None:
            verdict = '記事なし'
        elif '漫画' not in ext and 'マンガ' not in ext and 'コミック' not in ext:
            verdict = '非漫画'
        else:
            wy = parse_yomi(ext) or ''
            if not wy:
                verdict = 'よみ無'
            else:
                nw = norm(wy)
                madb_norms = [norm(m) for m in madb.split('|')]
                if nw == norm(s3):
                    verdict = '種3正しい'
                elif nw in madb_norms:
                    verdict = 'MADB一致(種3崩れ)'
                else:
                    verdict = '第3の読み'
        stats[verdict] = stats.get(verdict, 0) + 1
        w.writerow({'判定':verdict,'tier':r['tier'],'title':title,'種3現':s3,
                    'MADB読み':madb,'Wikipediaよみ':wy,'種a':sa})
        time.sleep(0.2)
        if (i+1) % 100 == 0:
            fo.flush()
            print(f'  {i+1}/{n} | ' + ' '.join(f'{k}:{v}' for k,v in sorted(stats.items())), flush=True)
    fo.close()
    print()
    print('=== 完了: Wikipedia 裁定 結果 ===')
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v:,}')
    print(f'  CSV: {OUT}')

if __name__ == '__main__':
    main()
