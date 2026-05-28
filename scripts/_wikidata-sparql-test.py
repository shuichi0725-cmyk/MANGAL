"""Wikidata SPARQL sample run = 手塚 Q193300 作品取得 + 英 label。

種3 内の qid (= 作者 qid) を SPARQL に投げて 作品 list + 英訳 取得テスト。
"""
import sys
import json
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path('.cache/wikidata-tezuka-sample.json')

SPARQL_URL = 'https://query.wikidata.org/sparql'
UA = 'MANGAL-research-bot/0.1 (https://github.com/shuichi0725-cmyk/MANGAL)'

QUERY = """
SELECT DISTINCT ?work ?workLabel ?ja_label ?en_label ?enwiki ?p31Label WHERE {
  ?work wdt:P50 wd:Q193300 .
  ?work wdt:P31 ?p31 .
  FILTER(?p31 IN (
    wd:Q8274,        # manga
    wd:Q1004,        # comics
    wd:Q14406742,    # manga series
    wd:Q21198342,    # manga magazine
    wd:Q562214,      # literary work
    wd:Q47461344,    # written work
    wd:Q838948       # work of art
  ))
  OPTIONAL { ?work rdfs:label ?ja_label . FILTER(LANG(?ja_label) = "ja") }
  OPTIONAL { ?work rdfs:label ?en_label . FILTER(LANG(?en_label) = "en") }
  OPTIONAL {
    ?enwiki schema:about ?work ;
            schema:isPartOf <https://en.wikipedia.org/> .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ja,en". }
}
LIMIT 1000
"""

def run_sparql(query: str) -> dict:
    params = urllib.parse.urlencode({'query': query, 'format': 'json'})
    url = f'{SPARQL_URL}?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def main():
    print('Running SPARQL: 手塚治虫 (Q193300) 作品取得...')
    result = run_sparql(QUERY)
    bindings = result['results']['bindings']
    print(f'結果: {len(bindings)} 作品 取得')

    # 整理
    works = []
    for b in bindings:
        work_uri = b.get('work', {}).get('value', '')
        wikidata_qid = work_uri.rsplit('/', 1)[-1] if work_uri else None
        ja = b.get('ja_label', {}).get('value', '')
        en = b.get('en_label', {}).get('value', '')
        enwiki = b.get('enwiki', {}).get('value', '')
        p31 = b.get('p31Label', {}).get('value', '')
        works.append({
            'qid': wikidata_qid,
            'ja_label': ja,
            'en_label': en,
            'enwiki': enwiki,
            'p31': p31,
        })

    # サンプル表示
    print()
    print('=== top 30 作品 ===')
    print(f'{"qid":12s} {"ja":30s} {"en":40s}')
    for w in works[:30]:
        ja = w['ja_label'][:30]
        en = w['en_label'][:40]
        print(f'{w["qid"] or "":12s} {ja:30s} {en:40s}')

    # en label がある率
    with_en = sum(1 for w in works if w['en_label'])
    with_ja = sum(1 for w in works if w['ja_label'])
    print()
    print(f'en label あり: {with_en}/{len(works)} ({with_en*100/len(works):.1f}%)')
    print(f'ja label あり: {with_ja}/{len(works)} ({with_ja*100/len(works):.1f}%)')

    OUT.write_text(json.dumps(works, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n→ {OUT} に出力')

if __name__ == '__main__':
    main()
