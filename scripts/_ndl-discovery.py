"""NDL SRU 新刊discovery(月分割・楽天速度): NDC726.1(漫画)を年月で引き、種2に無い新刊を発見。
★叩き速度=楽天と同じ1.2秒/req。500件窓は startRecord ページング＋(超過時)出版社/月で細分。
throttle回避: 1.2s・小バッチ・月分割・resumable(取得済ISBN skip)。NDL現在throttle中なら回復後に。
出力: data/seeds/ndl-discovery-<year>.tsv (isbn13/date/publisher/title/creators)
usage: python _ndl-discovery.py 2026          # 2026年の漫画新刊を月分割discovery
       python _ndl-discovery.py 2026 5 6       # 2026年5-6月のみ
"""
import sys, os, re, time, json, html, urllib.request, urllib.parse, sqlite3
ROOT = "C:/Users/shuic/code/MANGAL"
SRU = "https://ndlsearch.ndl.go.jp/api/sru"
RATE = 1.2  # ★楽天Books API と同じ。NDL遮断回避(per-ISBN burst 0.2sで429を踏んだ反省)。
WINDOW = 500  # NDL SRU 1照会の最大取得(maximumRecords上限)
YEAR = sys.argv[1] if len(sys.argv) > 1 else "2026"
M_FROM = int(sys.argv[2]) if len(sys.argv) > 2 else 1
M_UNTIL = int(sys.argv[3]) if len(sys.argv) > 3 else 12
OUT = f"{ROOT}/data/seeds/ndl-discovery-{YEAR}.tsv"

con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)
have = {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
seen = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        seen.add(l.split("\t")[0])

def sru(cql, start=1):
    p = {"operation": "searchRetrieve", "query": cql, "recordSchema": "dcndl",
         "maximumRecords": str(WINDOW), "startRecord": str(start)}
    url = SRU + "?" + urllib.parse.urlencode(p)
    for attempt in range(4):
        try:
            x = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MANGAL/1.0"}), timeout=60).read().decode("utf-8", "replace")
            time.sleep(RATE)  # ★楽天速度
            return html.unescape(x)
        except Exception as e:
            if "429" in str(e):
                print(f"  429 → {RATE*10}s backoff", flush=True)
            time.sleep(RATE * (attempt + 3))  # backoff
    return ""

def parse(xml):
    out = []
    for rec in re.findall(r"<recordData>(.*?)</recordData>", xml, re.S):
        ib = re.search(r'ISBN">([0-9\-]+)', rec)
        if not ib: continue
        isbn = re.sub(r"\D", "", ib.group(1))
        if len(isbn) != 13: continue
        t = re.search(r"<dcterms:title>([^<]+)", rec) or re.search(r"<dc:title>([^<]+)", rec)
        # ★kana: dc:title>rdf:Description>dcndl:transcription(題読み)
        km = re.search(r"<dc:title>.*?<dcndl:transcription>([^<]+)", rec, re.S)
        # ★出版社: dcterms:publisher>foaf:Agent>foaf:name
        pm = re.search(r"<dcterms:publisher>.*?<foaf:name>([^<]+)", rec, re.S) or re.search(r"<dcterms:publisher>([^<]+)", rec)
        # ★レーベル(コンビニ判定用): dcndl:seriesTitle>rdf:value
        sm = re.search(r"<dcndl:seriesTitle>.*?<rdf:value>([^<]+)", rec, re.S)
        vm = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)", rec, re.S)
        d = re.search(r"<dcterms:date>([^<]+)", rec) or re.search(r"<dcterms:issued[^>]*>([^<]+)", rec)
        # 著者(著者読みも拾う: dcterms:creator>foaf:name + transcription)
        cre = re.findall(r"<dcterms:creator>.*?<foaf:name>([^<]+)", rec, re.S) or re.findall(r"<dcterms:creator>([^<]+)", rec) or re.findall(r"<dc:creator>([^<]+)", rec)
        out.append({"isbn": isbn, "title": (t.group(1) if t else "").strip()[:80],
                    "kana": re.sub(r"\s+", "", km.group(1)).strip() if km else "",
                    "publisher": (pm.group(1).strip() if pm else ""),
                    "series": (sm.group(1).strip() if sm else ""),
                    "volume": (vm.group(1).strip() if vm else ""),
                    "date": d.group(1).strip() if d else "",
                    "creators": "/".join(c.strip()[:30] for c in cre[:5])})
    total = re.search(r"<numberOfRecords>(\d+)", xml)
    return out, int(total.group(1)) if total else 0

import datetime
fo = open(OUT, "a", encoding="utf-8")
if not seen: fo.write("isbn13\tdate\tpublisher\tseries\tvolume\ttitle\tkana\tcreators\n")
stat = {"new": 0, "req": 0}

def harvest_range(frm: datetime.date, until: datetime.date, depth: int = 0):
    """[frm,until) を NDC726.1で照会。total>500(窓超過)なら日付で半分割し再帰=全件カバー。"""
    cql = f'ndc=726.1 AND from="{frm.isoformat()}" AND until="{until.isoformat()}"'
    xml = sru(cql); stat["req"] += 1
    if not xml or "<diagnostic" in xml.lower():
        return
    recs, total = parse(xml)
    if total > WINDOW and (until - frm).days > 1 and depth < 8:
        # 窓超過→日付で半分割(再帰)。 全件取り切る。
        mid = frm + (until - frm) / 2
        harvest_range(frm, mid, depth + 1); harvest_range(mid, until, depth + 1)
        return
    # total<=500(窓内): startRecordページングで全件
    start = 1; got = 0
    while recs:
        for r in recs:
            if r["isbn"] in have or r["isbn"] in seen: continue
            seen.add(r["isbn"]); stat["new"] += 1
            fo.write(f"{r['isbn']}\t{r['date']}\t{r['publisher'][:20]}\t{r['series'][:24]}\t{r['volume']}\t{r['title'][:40]}\t{r['kana'][:40]}\t{r['creators'][:40]}\n")
        fo.flush(); got += len(recs); start += len(recs)
        if got >= total or len(recs) < WINDOW: break
        recs, total = parse(sru(cql, start)); stat["req"] += 1

for month in range(M_FROM, M_UNTIL + 1):
    f = datetime.date(int(YEAR), month, 1)
    u = datetime.date(int(YEAR) + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    harvest_range(f, u)
    print(f"  {YEAR}-{month:02d}完了: 新刊(種2外){stat['new']}累計 (req{stat['req']})", flush=True)
n_new, n_req = stat["new"], stat["req"]
fo.close()
print(f"完了: req{n_req} / 新刊候補{n_new}件 → {OUT}")
print(f"次=Stage2: 上記ISBNを SRU per-ISBN({RATE}s)で典拠ID enrich(homonym/clustering用)")
