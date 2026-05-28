"""Wikidata 代替経路 = wbgetentities + Wikipedia langlinks API。

SPARQL endpoint outage 回避のため、 直接 REST API で:
  1. 著者 qid から claims を取得 (wbgetentities)
  2. P800 (= notable work) や reverse-link で 作品 entity 取得
  3. 各作品の labels + sitelinks 取得

または Wikipedia 直接検索:
  https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=...
"""
import sys
import json
import urllib.parse
import urllib.request
from pathlib import Path
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path('.cache/wikidata-tezuka-v2.json')
UA = 'MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)'

def get_entity(qid: str) -> dict:
    """wbgetentities で entity 取得"""
    params = urllib.parse.urlencode({
        'action': 'wbgetentities',
        'ids': qid,
        'format': 'json',
        'props': 'labels|claims|sitelinks/urls|descriptions',
        'languages': 'ja|en',
    })
    url = f'https://www.wikidata.org/w/api.php?{params}'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def main():
    qid = 'Q193300'
    print(f'Fetching {qid} (手塚治虫) entity...')
    result = get_entity(qid)
    entity = result['entities'][qid]

    # labels
    labels = entity.get('labels', {})
    ja_label = labels.get('ja', {}).get('value', '')
    en_label = labels.get('en', {}).get('value', '')
    print(f'  ja label: {ja_label}')
    print(f'  en label: {en_label}')

    # P800 = notable work (= 主要作品)
    claims = entity.get('claims', {})
    notable_works = claims.get('P800', [])
    print(f'  P800 (notable work): {len(notable_works)} 件')
    work_qids = []
    for nw in notable_works:
        try:
            wqid = nw['mainsnak']['datavalue']['value']['id']
            work_qids.append(wqid)
        except (KeyError, TypeError):
            pass
    print(f'  → 作品 qid: {work_qids}')

    if not work_qids:
        print('NO notable works in P800 -- author entity does not have direct works')
        return

    # 各作品の entity 取得 (= rate limit に注意 = 1 req/sec)
    print()
    print('=== 各作品の labels + enwiki sitelink ===')
    print(f'{"qid":12s} {"ja":30s} {"en":35s} {"enwiki":35s}')
    works_out = []
    for wq in work_qids[:50]:  # 最大 50 件で抑制
        try:
            wr = get_entity(wq)
            ent = wr['entities'][wq]
            ja = ent.get('labels', {}).get('ja', {}).get('value', '')
            en = ent.get('labels', {}).get('en', {}).get('value', '')
            sitelinks = ent.get('sitelinks', {})
            enwiki = sitelinks.get('enwiki', {}).get('title', '')
            jawiki = sitelinks.get('jawiki', {}).get('title', '')
            works_out.append({
                'qid': wq, 'ja': ja, 'en': en, 'enwiki': enwiki, 'jawiki': jawiki,
            })
            print(f'{wq:12s} {ja[:30]:30s} {en[:35]:35s} {enwiki[:35]:35s}')
            time.sleep(0.3)  # be polite
        except Exception as e:
            print(f'  ERROR {wq}: {e}')

    OUT.write_text(json.dumps(works_out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n→ {OUT} に保存')

if __name__ == '__main__':
    main()
