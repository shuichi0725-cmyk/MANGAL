"""集英社 日本の歴史 を NDL SRU title検索で全巻取得し、 ISBN発行コードで年代版に補完。
NDL=古書/絶版に強い(楽天は絶版なし)。 書影のみ後で楽天ISBN直引き。 dry-run=結果表示。 --apply=preview反映。"""
import urllib.parse, urllib.request, html, re, json, time, sys, os, yaml, collections

ROOT = "C:/Users/shuic/code/MANGAL"
APPLY = "--apply" in sys.argv
SRU = "https://ndlsearch.ndl.go.jp/api/sru"

def code(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    return ib[6:10] if len(ib) == 13 else "?"

def fetch(start):
    q = {"operation": "searchRetrieve",
         "query": 'title="日本の歴史" AND title="集英社"',
         "recordSchema": "dcndl", "maximumRecords": "100", "startRecord": str(start)}
    req = urllib.request.Request(SRU + "?" + urllib.parse.urlencode(q))
    req.add_header("User-Agent", "Mozilla/5.0")
    return html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

# 全レコード収集(集英社 ISBN 9784-08 のみ)
records = []
start = 1
for _ in range(15):
    xml = fetch(start)
    recs = re.split(r"<recordData", xml)[1:]
    if not recs:
        break
    for r in recs:
        isbns = re.findall(r"(97[89][\d\-]{9,16})", r)
        isbns = [re.sub(r"\D", "", i) for i in isbns]
        isbns = [i for i in isbns if len(i) == 13 and i.startswith("9784")]
        if not isbns:
            continue
        ib = isbns[0]
        vol = None
        mv = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)</rdf:value>", r, re.S) or re.search(r"<dcndl:volume>\s*([^<]+?)\s*</dcndl:volume>", r)
        if mv:
            mn = re.search(r"\d+", mv.group(1))
            vol = int(mn.group()) if mn else None
        date = ""
        md = re.search(r"<dcterms:(?:issued|date)[^>]*>([^<]+)<", r) or re.search(r"<dc:date>([^<]+)<", r)
        if md:
            md2 = re.search(r"(\d{4})(?:[-.](\d{1,2}))?", md.group(1))
            if md2:
                date = md2.group(1) + (f"-{int(md2.group(2)):02d}" if md2.group(2) else "")
        title = ""
        mt = re.search(r"<dc:title>.*?<rdf:value>([^<]+)</rdf:value>", r, re.S) or re.search(r"<dc:title>([^<]+)</dc:title>", r)
        if mt:
            title = re.sub(r"<.*?>", "", mt.group(1)).strip()
        records.append({"isbn": ib, "vol": vol, "date": date, "title": title})
    got = len(recs)
    start += got
    time.sleep(1.2)
    if got < 100:
        break

# 集英社(9784-08)のみ・発行コードで年代版グループ
shu = [r for r in records if r["isbn"][4:6] == "08"]
byed = collections.defaultdict(dict)   # code -> {vol: rec}
for r in shu:
    if r["vol"]:
        byed[code(r["isbn"])].setdefault(r["vol"], r)

CODEMAP = {"2440": "1982年版", "1950": "1992年版", "1951": "1992年版", "2390": "1998年版", "7461": "2007年版 漫画版(文庫)", "2391": "2016年版 コンパクト"}
print(f"NDL取得 {len(records)}件 / 集英社 {len(shu)}件")
print("=== NDLで判明した集英社 日本の歴史 年代版(発行コード別 全巻) ===")
for c in sorted(byed, key=lambda k: -len(byed[k])):
    vols = sorted(byed[c])
    print(f"  [{CODEMAP.get(c, c)}] code{c}: {len(vols)}巻 {vols}")
json.dump({c: byed[c] for c in byed}, open(f"{ROOT}/.cache/nihonshi-ndl.json", "w", encoding="utf-8"), ensure_ascii=False, default=str)

if APPLY:
    # preview の nihonnorekishi 各年代版に NDL の欠巻を追加
    p = f"{ROOT}/.preview-data/manga/nihonnorekishi.yml"
    d = yaml.safe_load(open(p, encoding="utf-8"))
    label2code = {v: k for k, v in CODEMAP.items()}
    added = 0
    for e in d["editions"]:
        lab = e["label"].replace("日本の歴史 ", "")
        # この版の発行コード群
        codes = [c for c, l in CODEMAP.items() if l == lab]
        have = {v.get("number") for v in e["volumes"]}
        have_isbn = {re.sub(r"\D", "", str(v.get("isbn13") or "")) for v in e["volumes"]}
        for c in codes:
            for vol, r in byed.get(c, {}).items():
                if vol in have or r["isbn"] in have_isbn:
                    continue
                e["volumes"].append({"number": vol, "asin": None, "isbn13": r["isbn"], "cover_url": None, "release_date": r["date"] or None})
                have.add(vol); added += 1
        e["volumes"].sort(key=lambda v: v.get("number") or 0)
    yaml.safe_dump(d, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    print(f"\nAPPLIED: NDL欠巻 +{added}巻 → 各年代版補完")
    for e in d["editions"]:
        print(f"  [{e['label']}] {len(e['volumes'])}巻 {[v.get('number') for v in e['volumes']]}")
