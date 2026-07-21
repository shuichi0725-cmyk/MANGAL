"""NDL基点の巻補完(発見源で探す)。NDL discovery作の単巻/巻抜けページを
NDL SRU title検索で全巻ISBN取得 → 楽天ISBN直引きで書影/発売日 → 再構築。
★楽天title検索が0件のニッチ/表記揺れ作も拾える(キラーズホリディ型)。
[[ndl_volume_completion_better_than_rakuten]]。著者照合で別作混入防止・外れ値ガード。
usage: python _ndl-volume-complete.py [--apply]
"""
import os
import sys, re, json, time, glob, html, unicodedata, urllib.parse, urllib.request
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
PREV = f"{ROOT}/.preview-data/manga"
APPLY = "--apply" in sys.argv
SRU = "https://ndlsearch.ndl.go.jp/api/sru"
NRATE, RRATE = 1.5, 1.2
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"
EXCL = re.compile(r'セット|カレンダー|画集|原画集|アンソロジー|別冊|ガイド|ファンブック|設定資料|フェア|特装版|限定版|小説|ノベライズ|DVD付')

def norm(s):
    return re.sub(r'[\s　・,，\.。、:：;；!！?？’\'"()（）\[\]【】/／=～~\-]', '', unicodedata.normalize("NFKC", str(s or ""))).lower()

def base_title(t):
    t = re.sub(r'\s*[\.．。]?\s*第?\s*\d+\s*巻?\s*$', '', str(t or ''))
    return re.sub(r'[\s　\.．。]+$', '', t).strip()

def core_title(bt):
    c = re.split(r'[〜～:：]', str(bt))[0].strip()
    return c if len(c) >= 3 else str(bt)

def clean_author(a):
    return re.sub(r'\s*[\[【(（].*?[\]】)）]', '', str(a or '')).strip()

def ndl_title(core):
    q = {"operation": "searchRetrieve", "query": f'title="{core}"', "recordSchema": "dcndl",
         "maximumRecords": "100", "startRecord": "1"}
    req = urllib.request.Request(SRU + "?" + urllib.parse.urlencode(q)); req.add_header("User-Agent", "Mozilla/5.0 MANGAL")
    xml = html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    out = []
    for rd in re.split(r'<dcndl:BibResource ', xml)[1:]:
        t = re.search(r'<dc:title>(.*?)</dc:title>', rd, re.S) or re.search(r'<dcterms:title>(.*?)</dcterms:title>', rd, re.S)
        title = re.sub(r'<.*?>', '', t.group(1)).strip() if t else ''
        # ★dcndl:volume は <rdf:value>(巻) と <dcndl:transcription>(読み) を両方持つ → value のみ取る(二重化防止)
        vm = re.search(r'<dcndl:volume>.*?<rdf:value>(.*?)</rdf:value>', rd, re.S) or re.search(r'<dcndl:volume>([^<]*)</dcndl:volume>', rd, re.S)
        vol = re.sub(r'\D', '', unicodedata.normalize("NFKC", vm.group(1))) if vm else ''
        isbns = [re.sub(r'\D', '', x) for x in re.findall(r'ISBN[^>]*>\s*([\d\-]{10,17})', rd)]
        isbns = [x for x in isbns if len(x) == 13 and x.startswith('978')]
        creators = " ".join(re.sub(r'<.*?>', '', c) for c in re.findall(r'<dc:creator>(.*?)</dc:creator>', rd, re.S))
        dt = re.search(r'<dcterms:(?:date|issued)[^>]*>(\d{4})', rd)
        out.append({"title": title, "vol": int(vol) if vol else None, "isbns": isbns,
                    "creator": creators, "year": dt.group(1) if dt else None})
    return out

def rakuten_isbn(isbn):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "isbn": isbn,
         "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0 MANGAL")
    try:
        items = json.loads(urllib.request.urlopen(req, timeout=25).read()).get("Items") or []
    except Exception:
        return None, None
    if not items:
        return None, None
    it = items[0]
    cov = (it.get("largeImageUrl") or "").split("?")[0]
    sd = str(it.get("salesDate") or ""); m = re.match(r'(\d{4})年(\d{1,2})月', sd)
    return (cov if cov and "noimage" not in cov else None), (f"{m.group(1)}-{int(m.group(2)):02d}" if m else None)

# 対象 = 単巻 or 巻抜け
targets = []
for p in glob.glob(f"{PREV}/*.yml"):
    d = yaml.safe_load(open(p, encoding="utf-8"))
    if not d or d.get("source") != "ndl-discovery-2425":
        continue
    vn = sorted(v["number"] for e in (d.get("editions") or []) for v in (e.get("volumes") or []))
    if len(vn) <= 1 or (vn and max(vn) != len(vn)):
        targets.append((p, d))
print(f"対象(単巻/巻抜け): {len(targets)}", flush=True)

report = []
for i, (p, d) in enumerate(targets, 1):
    bt = base_title(d.get("title")); core = core_title(re.sub(r'[+＋]\s*$', '', bt).strip()); cn = norm(core)
    pauth = [norm(clean_author(a.get("name"))) for a in (d.get("authors") or []) if a.get("name")]
    try:
        recs = ndl_title(core)
    except Exception:
        report.append((d["slug"], bt, 0, "ERR")); time.sleep(NRATE * 2); continue
    # vol番号 -> ISBN (著者照合 + 題含有)
    vmap = {}
    for r in recs:
        if not r["isbns"] or EXCL.search(r["title"]):
            continue
        if cn not in norm(r["title"]):
            continue
        if pauth and r["creator"] and not any(pa and pa in norm(r["creator"]) for pa in pauth):
            continue
        v = r["vol"]
        if v is None:
            v = 1 if norm(r["title"]) == cn else None
        if v is None or v in vmap:
            continue
        vmap[v] = (r["isbns"][0], r["year"])
    # 外れ値除去
    if vmap:
        thr = max(len(vmap) * 1.8 + 3, 12)
        vmap = {k: v for k, v in vmap.items() if k <= thr}
    report.append((d["slug"], bt, len(vmap), sorted(vmap.keys())))
    if APPLY and len(vmap) >= 2:
        # ★既存巻(NDL-discovery原本=書影付)を seed → NDL発見の欠け巻だけ追加(マージ・既存優先)
        by_num = {v["number"]: v for e in (d.get("editions") or []) for v in (e.get("volumes") or [])}
        for n in sorted(vmap):
            if n in by_num:
                continue
            isbn, yr = vmap[n]
            cov, date = rakuten_isbn(isbn); time.sleep(RRATE)
            by_num[n] = {"number": n, "asin": None, "isbn13": isbn,
                         "cover_url": cov, "release_date": date or (f"{yr}" if yr else None)}
        vols = [by_num[k] for k in sorted(by_num)]
        d["title"] = bt
        for a in d.get("authors", []):
            a["name"] = clean_author(a.get("name", ""))
        d["editions"][0]["volumes"] = vols
        years = [int(str(v["release_date"])[:4]) for v in vols if v.get("release_date")]
        if years:
            d["year_started"] = min(years)
        yaml.safe_dump(d, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    if i % 20 == 0:
        print(f"  {i}/{len(targets)}", flush=True)
    time.sleep(NRATE)

multi = [r for r in report if isinstance(r[3], list) and r[2] > 1]
print(f"\nNDLで複数巻発見: {len(multi)} / 単巻のまま {len(report)-len(multi)}", flush=True)
for sl, bt, n, vs in sorted(report, key=lambda x: -(x[2] if isinstance(x[2], int) else 0))[:30]:
    print(f"  {n:2}巻 {bt[:26]:28} {vs if isinstance(vs,list) else vs}")
json.dump([(r[0], r[1], r[2], r[3]) for r in report], open(f"{ROOT}/.cache/ndl-vol-complete.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n{'APPLIED' if APPLY else 'DRY-RUN'} → .cache/ndl-vol-complete.json")
