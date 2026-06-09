"""NDL by-ISBN 照会 → 役割タグ付き著者 + 読み + 典拠ID をキャッシュ。 中断再開可。
入力 = .cache/polluted-isbns.json (案1 汚染シリーズの ISBN)
出力 = .cache/ndl-by-isbn.json  {isbn: {title, series, publisher, creators:[{name,role,yomi,authid}], raw_dc:[...]}}
NDL 不在は {} を記録(再照会しない)。 role は dc:creator 末尾の役割語から抽出。
"""
import urllib.request, urllib.parse, sys, re, time, json, os, html
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
ISBNS = json.load(open(ROOT + "/.cache/polluted-isbns.json", encoding="utf-8"))
CACHE = ROOT + "/.cache/ndl-by-isbn.json"
out = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
UA = {"User-Agent": "MANGAL-ndl/1.0 (manga DB enrichment)"}
ROLES = ["キャラクター原案", "原作", "原案", "漫画", "作画", "脚本", "構成", "監修",
         "編集", "編", "著者", "著", "画", "絵", "イラスト", "原著", "翻訳", "訳", "解説", "案", "作"]

def fetch(isbn):
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve"
           "&recordSchema=dcndl&maximumRecords=3&query=" + urllib.parse.quote("isbn=" + isbn))
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8")
    x = html.unescape(raw)
    nr = re.search(r"<numberOfRecords>(\d+)", x)
    if not nr or nr.group(1) == "0":
        return {}
    # 最初の BibResource ブロックのみ(maximumRecords=3 だが代表1件)
    title = re.search(r"<dcterms:title>(.*?)</dcterms:title>", x, re.S)
    title = title.group(1).strip() if title else ""
    series = re.search(r"<dcndl:seriesTitle>.*?<rdf:value>(.*?)</rdf:value>", x, re.S)
    series = series.group(1).strip() if series else ""
    pub = re.search(r"<dcterms:publisher>.*?<foaf:name>(.*?)</foaf:name>", x, re.S)
    pub = pub.group(1).strip() if pub else ""
    # dc:creator (display name + 役割語)
    dc = [re.sub(r"\s+", " ", c).strip() for c in re.findall(r"<dc:creator>(.*?)</dc:creator>", x, re.S)]
    # dcterms:creator foaf:Agent (典拠名 + 読み + authid)
    agents = []
    for blk in re.findall(r"<dcterms:creator>(.*?)</dcterms:creator>", x, re.S):
        nm = re.search(r"<foaf:name>(.*?)</foaf:name>", blk, re.S)
        yomi = re.search(r"<dcndl:transcription>(.*?)</dcndl:transcription>", blk, re.S)
        aid = re.search(r"id\.ndl\.go\.jp/auth/entity/(\d+)", blk)
        if nm:
            agents.append({"auth_name": nm.group(1).strip(),
                           "yomi": yomi.group(1).strip() if yomi else "",
                           "authid": aid.group(1) if aid else ""})
    creators = []
    for i, s in enumerate(dc):
        role = ""
        for r in ROLES:
            if s.endswith(" " + r) or s.endswith("　" + r) or s == r:
                role = r
                name = s[: -len(r)].strip().rstrip(",、 　")
                break
        else:
            name = s
        ag = agents[i] if i < len(agents) else {}
        creators.append({"name": name, "role": role,
                         "yomi": ag.get("yomi", ""), "authid": ag.get("authid", ""),
                         "auth_name": ag.get("auth_name", "")})
    return {"title": title, "series": series, "publisher": pub,
            "creators": creators, "raw_dc": dc}

todo = [i for i in ISBNS if i not in out]
print("対象 %d / 既取得 %d / 残 %d" % (len(ISBNS), len(out), len(todo)), flush=True)
hit = 0
for n, isbn in enumerate(todo, 1):
    try:
        out[isbn] = fetch(isbn)
        if out[isbn]:
            hit += 1
    except Exception as e:
        out[isbn] = {"_err": str(e)[:80]}
    time.sleep(0.35)
    if n % 100 == 0:
        json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d hit=%d" % (n, len(todo), hit), flush=True)
json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
got = sum(1 for v in out.values() if v and "_err" not in v)
print("完了: 取得%d / 試行%d / NDL不在or誤%d" % (got, len(out), len(out) - got), flush=True)
