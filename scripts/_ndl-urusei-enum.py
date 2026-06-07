"""うる星やつら の全版・全刷を NDL by-title で網羅取得し、出版社×レーベル(刷)で整理。
MADB未収録の新装版・重版も拾う。出力: .cache/ndl-urusei.json + 集計表示。
"""
import sys, json, re, html, time
import urllib.request, urllib.parse
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

def field(rc, tag):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), rc, re.S)
    return m.group(1).strip() if m else ""

def subval(rc, tag):
    m = re.search(r"<%s>.*?<rdf:value>(.*?)</rdf:value>" % tag, rc, re.S)
    return m.group(1).strip() if m else ""

def pub_of(rc):
    m = re.search(r"<dcterms:publisher>.*?<foaf:name>(.*?)</foaf:name>", rc, re.S)
    return m.group(1).strip() if m else ""

records = []
start = 1
while True:
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl"
           "&maximumRecords=200&startRecord=%d&query=%s"
           % (start, urllib.parse.quote('title="うる星やつら"')))
    x = html.unescape(urllib.request.urlopen(url, timeout=60).read().decode("utf-8"))
    total = re.search(r"<numberOfRecords>(\d+)</numberOfRecords>", x)
    total = int(total.group(1)) if total else 0
    recs = re.split(r'<dcndl:BibResource rdf:about="[^"]*#material"', x)[1:]
    for rc in recs:
        isbn = re.search(r'ISBN\">([\d\-Xx]+)<', rc)
        records.append({
            "isbn": (isbn.group(1).replace("-", "") if isbn else ""),
            "title": field(rc, "dcterms:title"),
            "pub": pub_of(rc),
            "series": subval(rc, "dcndl:seriesTitle"),
            "vol": subval(rc, "dcndl:volume"),
            "date": field(rc, "dcterms:date"),
            "creator": " ".join(re.findall(r"<dc:creator>(.*?)</dc:creator>", rc)),
            "ndc": ",".join(re.findall(r"ndc\d*/([\d.]+)", rc)),
            "ext": field(rc, "dcterms:extent"),
        })
    print("取得 %d / 総 %d" % (len(records), total))
    if start + 200 > total:
        break
    start += 200
    time.sleep(0.4)

json.dump(records, open(".cache/ndl-urusei.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 漫画(NDC726 or 高橋留美子)に絞り、出版社×レーベルで集計
mang = [r for r in records if "726" in r["ndc"] or "高橋留美子" in r["creator"]]
print("\n=== 漫画レコード:", len(mang), "(全%d中)" % len(records))
grp = defaultdict(list)
for r in mang:
    grp[(r["pub"], r["series"])].append(r)
print("\n=== 出版社 × レーベル(刷/版)ごと ===")
for (pub, ser), items in sorted(grp.items(), key=lambda x: -len(x[1])):
    yrs = sorted(set(i["date"][:4] for i in items if i["date"]))
    isbns = [i["isbn"] for i in items if i["isbn"]]
    print("  出版社=%-10s レーベル=%-30s %d冊 (%s%s) ISBN例=%s"
          % (pub or "?", (ser or "(無)")[:30], len(items),
             yrs[0] if yrs else "?", ("-" + yrs[-1]) if len(yrs) > 1 else "",
             isbns[0] if isbns else "無"))
