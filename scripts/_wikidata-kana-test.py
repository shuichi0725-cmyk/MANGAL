"""Wikidata で 漫画作品の かな表記 (P1814) が 一括取得できるか 試験。

P1814 = name in kana (= 読み仮名)。 これが 漫画作品に どれだけあるか。
あれば SPARQL 一括取得 → 種3 フリガナ照合 で 正当性向上に使える。
"""
import sys, json, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

SPARQL = 'https://query.wikidata.org/sparql'
UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'

def run(query):
    params = urllib.parse.urlencode({'query': query, 'format': 'json'})
    req = urllib.request.Request(f'{SPARQL}?{params}',
        headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())

# 1) 漫画作品 (manga series 等) で P1814 (かな) を持つ件数
COUNT_Q = """
SELECT (COUNT(DISTINCT ?work) AS ?c) WHERE {
  ?work wdt:P31/wdt:P279* wd:Q21198342 .   # manga series (サブクラス含む)
  ?work wdt:P1814 ?kana .
}
"""
# 2) サンプル (label + kana)
SAMPLE_Q = """
SELECT ?work ?workLabel ?kana WHERE {
  ?work wdt:P31/wdt:P279* wd:Q21198342 .
  ?work wdt:P1814 ?kana .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ja". }
}
LIMIT 40
"""
# 3) 比較: P1814 無視で manga series 総数 (= カバー率分母)
TOTAL_Q = """
SELECT (COUNT(DISTINCT ?work) AS ?c) WHERE {
  ?work wdt:P31/wdt:P279* wd:Q21198342 .
}
"""

def main():
    print('Wikidata SPARQL 試験...', flush=True)
    try:
        total = int(run(TOTAL_Q)['results']['bindings'][0]['c']['value'])
        print(f'manga series 総数 (Wikidata): {total:,}')
    except Exception as e:
        print(f'TOTAL query error: {e}')
        total = 0
    try:
        c = int(run(COUNT_Q)['results']['bindings'][0]['c']['value'])
        print(f'うち P1814(かな) あり: {c:,}' + (f' ({c*100/total:.1f}%)' if total else ''))
    except Exception as e:
        print(f'COUNT query error: {e}')
        c = 0
    print()
    print('=== P1814 サンプル (label / かな) ===')
    try:
        for b in run(SAMPLE_Q)['results']['bindings'][:40]:
            label = b.get('workLabel', {}).get('value', '')
            kana = b.get('kana', {}).get('value', '')
            print(f'  {label!r}  → {kana!r}')
    except Exception as e:
        print(f'SAMPLE query error: {e}')

if __name__ == '__main__':
    main()
