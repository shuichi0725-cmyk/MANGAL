"""Wikidata の P1814(かな表記) 付き 漫画作品を 1クエリで 一括取得。
outage 中の rate-limit (1req/min) 対策で 単発クエリ。
"""
import sys, json, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'
Q = """
SELECT ?work ?workLabel ?kana WHERE {
  ?work wdt:P31/wdt:P279* wd:Q21198342 .
  ?work wdt:P1814 ?kana .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ja". }
}
LIMIT 20000
"""

def main():
    params = urllib.parse.urlencode({'query': Q, 'format': 'json'})
    req = urllib.request.Request('https://query.wikidata.org/sparql?' + params,
        headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
    except Exception as e:
        print(f'ERROR: {e}')
        return
    b = d['results']['bindings']
    out = [{'label': x.get('workLabel', {}).get('value', ''),
            'kana': x.get('kana', {}).get('value', '')} for x in b]
    open('.cache/wikidata-manga-kana.json', 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False))
    print(f'P1814(かな) 付き 漫画作品: {len(out):,} 件 取得')
    print()
    print('=== サンプル 40 (label → かな) ===')
    for x in out[:40]:
        print(f'  {x["label"]!r}  →  {x["kana"]!r}')

if __name__ == '__main__':
    main()
