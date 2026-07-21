"""NDL登録日ハーベスタ(Stage1): OAI-PMHで「NDLが書誌を登録した日(datestamp)」範囲をバルク取得。
★throttle回避(オープンデータ)・叩き速度=楽天と同じ1.2秒/req・resumptionToken loop・resumable。
削除(status=deleted)skip / 漫画フィルタ(NDC726 ∨ Cコード97xx) / 種2 ISBN dedup。
出力: .cache/ndl-oai/registered-<from>_<until>.jsonl (新刊候補: isbn/title/vol/publisher/creators/datestamp)
usage: python _harvest-ndl-oai-registration.py <from-date> <until-date>   例: 2025-05-01 2025-06-01
Stage2(典拠enrich)は別途 SRU per-ISBN(同1.2s)で新刊ISBNのみ。"""
import urllib.request, urllib.parse, re, time, json, os, sys, sqlite3, html
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
RATE = 1.2  # ★楽天Books API と同じ 1req/sec 余裕(1.2s)。NDL礼儀・遮断回避。
OAI = "https://ndlsearch.ndl.go.jp/api/oaipmh"
FROM = sys.argv[1] if len(sys.argv) > 1 else "2025-05-01"
UNTIL = sys.argv[2] if len(sys.argv) > 2 else "2025-06-01"
os.makedirs(f"{ROOT}/.cache/ndl-oai", exist_ok=True)
OUT = f"{ROOT}/.cache/ndl-oai/registered-{FROM}_{UNTIL}.jsonl"

# 種2既存ISBN(dedup用)
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)
have = {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}

def fetch(params):
    url = OAI + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MANGAL/1.0"}), timeout=60).read().decode("utf-8", "replace")
        except Exception as e:
            time.sleep(RATE * (attempt + 2))  # backoff
    return ""

def parse_records(xml):
    out = []
    for rec in re.findall(r"<record>(.*?)</record>", xml, re.S):
        if 'status="deleted"' in rec:
            continue  # 削除レコードskip
        meta = rec  # dcndl metadata部
        def g(tag):
            m = re.search(rf"<{tag}[^>]*>([^<]+)", meta)
            return html.unescape(m.group(1).strip()) if m else None
        isbns = re.findall(r"(978[0-9]{10})", re.sub(r"[^0-9A-Za-z<>:/]", "", meta))
        ndc = bool(re.search(r"726", meta))
        ccode = bool(re.search(r"[Cc]9[0-9]{3}", meta))
        if not (ndc or ccode):
            continue  # 漫画signal無→skip(NDC726 ∨ Cコード97xx)
        title = g("dcterms:title") or g("dc:title")
        creators = re.findall(r"<dcterms:creator[^>]*>([^<]+)", meta) or re.findall(r"<dc:creator>([^<]+)", meta)
        ds = g("datestamp")
        for ib in isbns:
            if ib in have:
                continue  # 種2 dedup
            out.append({"isbn": ib, "title": (title or "")[:80], "publisher": g("dcterms:publisher") or g("dc:publisher"),
                        "volume": g("dcndl:volume"), "creators": [html.unescape(c)[:30] for c in creators[:5]],
                        "ndc726": ndc, "ccode97": ccode, "datestamp": ds})
    return out

# resumptionToken loop
n_req = n_rec = n_manga = 0
token = None
fo = open(OUT, "w", encoding="utf-8")
while True:
    params = {"verb": "ListRecords", "resumptionToken": token} if token else \
             {"verb": "ListRecords", "metadataPrefix": "dcndl", "from": f"{FROM}T00:00:00Z", "until": f"{UNTIL}T00:00:00Z"}
    xml = fetch(params); n_req += 1
    if not xml or "<error" in xml:
        err = re.search(r'<error[^>]*>([^<]+)', xml or "")
        print(f"  停止: {err.group(1) if err else 'empty/err'} (req {n_req})", flush=True)
        break
    recs = parse_records(xml)
    for r in recs:
        fo.write(json.dumps(r, ensure_ascii=False) + "\n"); n_manga += 1
    n_rec += len(re.findall(r"<record>", xml))
    fo.flush()
    if n_req % 10 == 0:
        print(f"  req{n_req} 走査{n_rec} 漫画新刊{n_manga}", flush=True)
    tm = re.search(r"<resumptionToken[^>]*>([^<]+)</resumptionToken>", xml)
    token = tm.group(1) if tm else None
    time.sleep(RATE)  # ★楽天と同じ叩き速度
    if not token:
        break
fo.close()
print(f"完了: req{n_req} / 走査{n_rec}レコード / 漫画新刊候補{n_manga}件 → {OUT}", flush=True)
print(f"次=Stage2: 上記ISBNを SRU per-ISBN({RATE}s)で典拠ID enrich")
