#!/usr/bin/env python3
"""
REPOINT_full 38 の自前ISBN調査 (NDL SRU 一次、READ-ONLY)。
各slugの題でNDL照会→各書誌の著者(name+ヨミ)・ISBN・年・出版社を取得し、
slug著者(name+kana)と name/ヨミ で照合 → 自前ISBN(own) と別著者(other) に仕分け。
NDLは絶版でも収録(=楽天在庫切れ対策の本命)。著者ヨミでペンネーム/かな漢字も裁定。
出力: .cache/_repoint_ndl.json
"""
import sys, json, re, unicodedata, urllib.request, urllib.parse, time
from pathlib import Path
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
NS = {'dc': 'http://purl.org/dc/elements/1.1/', 'dcterms': 'http://purl.org/dc/terms/',
      'dcndl': 'http://ndl.go.jp/dcndl/terms/', 'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
      'foaf': 'http://xmlns.com/foaf/0.1/'}

def kata(s):  # ひらがな→カタカナ + NFKC + 記号除去
    s = unicodedata.normalize('NFKC', str(s or ''))
    s = re.sub(r'[ぁ-ん]', lambda m: chr(ord(m.group())+0x60), s)
    return re.sub(r'[\s　・,，、।\-/／･]', '', s)
def nm(s):  # 名前正規化(異体字+空白)
    VAR = str.maketrans('髙﨑德濵齋齊', '高崎徳浜斎斉')
    return re.sub(r'[\s　・]', '', unicodedata.normalize('NFKC', str(s or '')).translate(VAR))
def to13(s):
    s = str(s or '').replace('-', '').strip()
    if len(s) == 13 and s.isdigit(): return s
    return ''
def i10to13(s):
    s = str(s or '').replace('-', '').strip()
    if len(s) == 10:
        core = '978' + s[:9]
        t = sum((1 if i % 2 == 0 else 3)*int(c) for i, c in enumerate(core))
        return core + str((10-t % 10) % 10)
    return to13(s)

def sru(cql, n=50):
    q = urllib.parse.urlencode({'operation': 'searchRetrieve', 'recordSchema': 'dcndl', 'maximumRecords': str(n), 'query': cql})
    req = urllib.request.Request('https://ndlsearch.ndl.go.jp/api/sru?'+q, headers={'User-Agent': 'mangal-research/1.0'})
    return urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
def val(e):
    if e is None: return ''
    v = e.find('rdf:Description/rdf:value', NS)
    return (v.text if v is not None and v.text else (e.text or '')).strip()
def parse(x):
    out = []
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
                    name = val(ag.find('foaf:name', NS)); yomi = val(ag.find('dcndl:transcription', NS))
                    if name: crs.append((name, yomi))
                elif c.text: crs.append((c.text.strip(), ''))
            isbns = [i10to13(i.text) for i in res.findall('dcterms:identifier', NS)
                     if 'ISBN' in i.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}datatype', '') and i.text]
            isbns = [i for i in isbns if i]
            pub = val(res.find('dcterms:publisher/foaf:Agent/foaf:name', NS))
            date = val(res.find('dcterms:issued', NS))
            vol = val(res.find('dcndl:volume', NS))
            out.append({'title': t, 'creators': crs, 'isbns': isbns, 'pub': pub, 'date': date, 'vol': vol})
    return out

meta = json.load(open(ROOT/'.cache/_repoint38.json', encoding='utf-8'))
results = {}
for i, m in enumerate(meta):
    sl = m['slug']
    if m.get('err'): continue
    title = m['title'] or ''
    # 題core(英数記号除いた主要部、先頭8〜文字)。括弧subtitle除去
    core = re.sub(r'[（(].*$', '', title).strip()
    core = re.sub(r'[ 　:：].*$', '', core).strip() or title
    sa_names = [nm(a[0]) for a in (m['authors'] or []) if a[0]]
    sa_yomi = [kata(a[1]) for a in (m['authors'] or []) if a[1]]
    sa_kata_name = [kata(a[0]) for a in (m['authors'] or []) if a[0]]
    try:
        recs = parse(sru(f'title="{core}"'))
    except Exception as e:
        results[sl] = {'err': str(e)}; continue
    own, other = [], []
    for r in recs:
        matched = False
        for cn, cy in r['creators']:
            cnn = nm(cn); cyk = kata(cy); cnk = kata(cn)
            if any(s and (s in cnn or cnn in s) for s in sa_names): matched = True; break
            if cyk and any(s and (s in cyk or cyk in s) for s in sa_yomi+sa_kata_name): matched = True; break
            if cnk and any(s and (s in cnk or cnk in s) for s in sa_kata_name+sa_yomi): matched = True; break
        (own if matched else other).append(r)
    results[sl] = {'title': title, 'slug_authors': m['authors'], 'core': core,
                   'own': own, 'other_count': len(other),
                   'other_sample': [(r['title'][:24], r['creators'][:1], r['isbns'][:1]) for r in other[:3]]}
    time.sleep(0.4)
    print(f'[{i+1}/38] {sl}: own={len(own)} other={len(other)}', flush=True)

json.dump(results, open(ROOT/'.cache/_repoint_ndl.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('done')
