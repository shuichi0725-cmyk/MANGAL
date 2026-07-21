# -*- coding: utf-8 -*-
# band-intruders 96作のNDL harvest(再開可能・1.3s・429即中断)
import csv, json, os, re, sys, time, html, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
OUT = f'{ROOT}/.cache/intruder-ndl.jsonl'

slugs = sorted({r[0] for r in csv.reader(open(f'{ROOT}/docs/production-diagnostics/band-intruders.tsv', encoding='utf-8'), delimiter='\t') if r and r[0] != 'slug'})
done = set()
if os.path.exists(OUT):
    for ln in open(OUT, encoding='utf-8'):
        done.add(json.loads(ln)['slug'])

def sru(q):
    p = {'operation': 'searchRetrieve', 'query': q, 'recordSchema': 'dcndl', 'maximumRecords': '200'}
    req = urllib.request.Request('https://ndlsearch.ndl.go.jp/api/sru?' + urllib.parse.urlencode(p))
    req.add_header('User-Agent', 'Mozilla/5.0')
    return html.unescape(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))

fo = open(OUT, 'a', encoding='utf-8')
for i, s in enumerate(slugs):
    if s in done:
        continue
    d = yaml.safe_load(open(f'{ROOT}/data/manga.v2/{s}.yml', encoding='utf-8'))
    title = d.get('title') or ''
    creator = (d.get('authors') or [{}])[0].get('name') or ''
    recs = []
    for q in (f'title="{title}" AND creator="{creator}"',):
        try:
            xml = sru(q)
        except Exception as e:
            print(f'  {s}: query失敗スキップ {e}')
            time.sleep(2)
            continue
        if 'Too Many Requests' in xml:
            print('★429→中断(逐次保存済)'); fo.close(); sys.exit(2)
        for r in re.split(r'<dcndl:BibResource', xml)[1:]:
            g = lambda pat: (re.search(pat, r, re.S).group(1) if re.search(pat, r, re.S) else '')
            recs.append({'title': g(r'<dcterms:title>([^<]+)'), 'vol': g(r'<dcndl:volume>.*?<rdf:value>([^<]+)'),
                         'date': g(r'<dcterms:date>([^<]+)'), 'isbn': re.sub(r'[^0-9X]', '', g(r'(97[89][\d\-]{10,16})')),
                         'pub': g(r'<foaf:name>([^<]+)')})
        time.sleep(1.3)
    fo.write(json.dumps({'slug': s, 'title': title, 'creator': creator, 'records': recs}, ensure_ascii=False) + '\n')
    fo.flush()
    if (i + 1) % 10 == 0:
        print(f'{i+1}/{len(slugs)}', flush=True)
fo.close()
print(f'完了 {len(slugs)}作')
