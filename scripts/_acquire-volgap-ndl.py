"""巻抜け全作のNDL正データを作品名で取得(全版・全巻=ISBN/出版社/発売日/巻label/叢書/題)。
per-case是正の土台。 中断耐性=JSONL追記・resume。 NDL 1.2s/req厳守。
出力: .cache/volgap-ndl.jsonl ({slug, title, records:[{isbn,publisher,date,volume,series,ndl_title}]})"""
import json, re, os, time, html, urllib.parse, urllib.request, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
SRU = "https://ndlsearch.ndl.go.jp/api/sru"
OUT = f"{ROOT}/.cache/volgap-ndl.jsonl"

done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try:
            done.add(json.loads(l)["slug"])
        except Exception:
            pass

rows = [l.rstrip("\n").split("\t") for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap.tsv", encoding="utf-8")][1:]
todo = [(r[0], r[1]) for r in rows if r[0] not in done]
print(f"巻抜け {len(rows)} / 取得済 {len(done)} / 残 {len(todo)}", flush=True)

def fetch(title, start):
    q = {"operation": "searchRetrieve", "query": f'title="{title}"', "recordSchema": "dcndl", "maximumRecords": "50", "startRecord": str(start)}
    req = urllib.request.Request(SRU + "?" + urllib.parse.urlencode(q)); req.add_header("User-Agent", "Mozilla/5.0")
    return html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

def parse(r):
    isbns = [re.sub(r"\D", "", i) for i in re.findall(r"(97[89][\d\-]{9,16})", r)]
    isbns = [i for i in isbns if len(i) == 13]
    pub = re.search(r"<dcterms:publisher>.*?<foaf:name>([^<]+)", r, re.S) or re.search(r"<dc:publisher>([^<]+)", r)
    dt = re.search(r"<dcterms:(?:issued|date)[^>]*>([^<]+)", r) or re.search(r"<dc:date>([^<]+)", r)
    vol = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)", r, re.S)
    ser = re.search(r"<dcndl:seriesTitle>([^<]+)", r)
    tit = re.search(r"<dc:title>.*?<rdf:value>([^<]+)", r, re.S) or re.search(r"<dc:title>([^<]+)", r)
    return {"isbn": isbns[0] if isbns else None,
            "publisher": (pub.group(1).strip() if pub and pub.group(1).strip() != "国立国会図書館" else (pub.group(1).strip() if pub else "")),
            "date": (dt.group(1)[:7] if dt else ""),
            "volume": vol.group(1).strip() if vol else "",
            "series": re.sub(r"<.*?>", "", ser.group(1))[:30] if ser else "",
            "ndl_title": re.sub(r"<.*?>", "", tit.group(1))[:40] if tit else ""}

f = open(OUT, "a", encoding="utf-8")
n = 0
for sl, title in todo:
    recs = []
    start = 1
    try:
        for _ in range(5):
            xml = fetch(title, start)
            chunk = re.split(r"<recordData", xml)[1:]
            if not chunk:
                break
            for r in chunk:
                recs.append(parse(r))
            if len(chunk) < 50:
                break
            start += len(chunk); time.sleep(1.2)
    except Exception as e:
        recs = recs or []
    f.write(json.dumps({"slug": sl, "title": title, "records": recs}, ensure_ascii=False) + "\n")
    f.flush()
    n += 1
    if n % 50 == 0:
        print(f"  {n}/{len(todo)} 取得 (直近 {title[:16]} {len(recs)}件)", flush=True)
    time.sleep(1.2)
f.close()
print(f"完了: {n}作 取得 → {OUT}", flush=True)
