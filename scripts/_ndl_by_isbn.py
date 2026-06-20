#!/usr/bin/env python3
"""
NDL ISBN直引き(権威的著者名+ヨミ取得)。.cache/_unresolved_isbns.txt の各ISBNをNDL SRUで引き、
{isbn: {title, authors:[(name,yomi)], pub, date}} を .cache/_ndl_isbn_map.json に出力。READ-ONLY。
著者ヨミで異体字(高橋/髙橋)を裁定可能にする。中断耐性=既取得分はskip。
"""
import sys, json, re, urllib.request, urllib.parse, time
from pathlib import Path
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
NS = {'dcterms': 'http://purl.org/dc/terms/', 'dcndl': 'http://ndl.go.jp/dcndl/terms/',
      'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'foaf': 'http://xmlns.com/foaf/0.1/'}
def val(e):
    if e is None: return ''
    v = e.find('rdf:Description/rdf:value', NS)
    return (v.text if v is not None and v.text else (e.text or '')).strip()
def sru(cql):
    q = urllib.parse.urlencode({'operation': 'searchRetrieve', 'recordSchema': 'dcndl', 'maximumRecords': '5', 'query': cql})
    return urllib.request.urlopen(urllib.request.Request('https://ndlsearch.ndl.go.jp/api/sru?'+q, headers={'User-Agent': 'mangal/1.0'}), timeout=40).read().decode('utf-8')
def parse(x):
    for rd in ET.fromstring(x).iter('{http://www.loc.gov/zing/srw/}recordData'):
        try: rdf = ET.fromstring(''.join(rd.itertext()))
        except: continue
        for res in rdf.iter('{http://ndl.go.jp/dcndl/terms/}BibResource'):
            t = val(res.find('dcterms:title', NS))
            if not t: continue
            crs = []
            for c in res.findall('dcterms:creator', NS):
                ag = c.find('foaf:Agent', NS)
                if ag is not None:
                    crs.append((val(ag.find('foaf:name', NS)), val(ag.find('dcndl:transcription', NS))))
                elif c.text: crs.append((c.text.strip(), ''))
            return {'title': t, 'authors': crs, 'pub': val(res.find('dcterms:publisher/foaf:Agent/foaf:name', NS)), 'date': val(res.find('dcterms:issued', NS))}
    return None

isbns = ROOT.joinpath('.cache/_unresolved_isbns.txt').read_text().split()
outp = ROOT/'.cache/_ndl_isbn_map.json'
m = json.load(open(outp, encoding='utf-8')) if outp.exists() else {}
todo = [i for i in isbns if i not in m]
print(f'todo {len(todo)} / 既 {len(m)}', flush=True)
for n, ib in enumerate(todo):
    try: m[ib] = parse(sru(f'isbn="{ib}"'))
    except Exception as e: m[ib] = {'err': str(e)}
    if n % 50 == 49:
        json.dump(m, open(outp, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'  {n+1}/{len(todo)}', flush=True)
    time.sleep(0.25)
json.dump(m, open(outp, 'w', encoding='utf-8'), ensure_ascii=False)
print('done', len(m))
