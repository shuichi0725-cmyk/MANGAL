"""NDL preview の単巻ページを、楽天 題+著者検索で全巻補完。
NDL発見ISBNは多巻シリーズの1冊(vol1とは限らず第13巻等)なので、題+著者で全巻を集め editions を再構築。
- セット/カレンダー/画集/アンソロジー/別冊 は除外。 978-prefix のみ(セット品コード2100…除外)。
- 題NFKC前方一致 + 著者ゆるく一致 で別作混入を防ぐ。 巻番号=第N巻/.N/末尾数字、無印=1。
- dry-run(既定)で巻数report、 --apply で .preview-data 再構築。 1.2s/req・resumable。
"""
import sys, re, json, time, glob, unicodedata, urllib.parse, urllib.request
import yaml
ROOT = "C:/Users/shuic/code/MANGAL"
PREV = f"{ROOT}/.preview-data/manga"
APPLY = "--apply" in sys.argv
RATE = 1.2
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"
EXCL = re.compile(r'セット|カレンダー|画集|原画集|アンソロジー|別冊|ガイド|ファンブック|設定資料|フェア|特装版|限定版|小説|ノベライズ')

def norm(s):
    return re.sub(r'[\s　・,，\.。、:：;；!！?？’\'"()（）\[\]【】/／=～~-]', '', unicodedata.normalize("NFKC", str(s or ""))).lower()

def base_title(t):
    t = str(t or '')
    t = re.sub(r'\s*[\.．。]?\s*第?\s*\d+\s*巻?\s*$', '', t)   # 末尾 第N巻 / .N / 。N
    t = re.sub(r'[\s　\.．。]+$', '', t)
    return t.strip()

def clean_author(a):
    return re.sub(r'\s*[\[【].*?[\]】]', '', str(a or '')).strip()

def search(title, author=""):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "title": title,
         "outOfStockFlag": "1", "hits": "30", "format": "json", "formatVersion": "2"}
    if author:
        p["author"] = author
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0 MANGAL")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())

def vol_of(rk_title, base_norm):
    t = unicodedata.normalize("NFKC", str(rk_title))
    # ① 第N巻  ② (N)  ③ 末尾N(任意区切り後)  ④ base除去後の先頭数字  ⑤ 無印=1
    m = re.search(r'第\s*(\d+)\s*巻', t)
    if m: return int(m.group(1))
    m = re.search(r'[(\[]\s*(\d+)\s*[)\]]', t)
    if m: return int(m.group(1))
    m = re.search(r'(\d+)\s*$', t)            # 末尾数字 (題〜副題〜2 / 題、1 / 題 8 を捕捉)
    if m: return int(m.group(1))
    rest = norm(t)
    if rest.startswith(base_norm):
        tail = rest[len(base_norm):]
        m = re.match(r'(\d+)', tail)          # base直後の数字 (カドル4-獣人… 型)
        if m: return int(m.group(1))
        if not re.search(r'\d', tail):        # base題そのもの = 1巻
            return 1
    return None

def parse_date(s):
    s = str(s or '').replace('年', '-').replace('月', '-').replace('日', '')
    m = re.match(r'(\d{4})-?(\d{1,2})?-?(\d{1,2})?', s)
    if not m:
        return None
    return f"{m.group(1)}" + (f"-{int(m.group(2)):02d}" if m.group(2) else "") + (f"-{int(m.group(3)):02d}" if m.group(2) and m.group(3) else "")

# 対象 = NDL preview の単巻ページ
targets = []
for p in glob.glob(f"{PREV}/*.yml"):
    d = yaml.safe_load(open(p, encoding="utf-8"))
    if not d or d.get("source") != "ndl-discovery-2425":
        continue
    nvol = sum(len(e.get("volumes") or []) for e in (d.get("editions") or []))
    if nvol <= 1:
        targets.append((p, d))
print(f"単巻NDLページ: {len(targets)}", flush=True)

report = []
for i, (p, d) in enumerate(targets, 1):
    bt = base_title(d.get("title"))
    author = clean_author((d.get("authors") or [{}])[0].get("name", ""))
    bn = norm(bt)
    page_plus = bool(re.search(r'[+＋]\s*$', unicodedata.normalize("NFKC", str(d.get("title")))))
    sbt = re.sub(r'[+＋]\s*$', '', bt).strip()   # 検索用は+除去
    try:
        items = (search(sbt, author).get("Items") or [])
        if len(items) < 2:                        # 著者付きで少ない→題のみ再検索
            items = (search(sbt, "").get("Items") or [])
    except Exception as e:
        report.append((d["slug"], bt, 0, "ERR")); time.sleep(RATE * 2); continue
    vols = {}
    for it in items:
        ti = it.get("title", ""); isbn = re.sub(r"\D", "", str(it.get("isbn") or ""))
        if len(isbn) != 13 or not isbn.startswith("978"):
            continue
        if EXCL.search(ti):
            continue
        if not norm(ti).startswith(bn):   # 別作除外(題前方一致)
            continue
        # ＋スピンオフ判別: ページが＋系なら＋付きのみ、 そうでなければ＋無しのみ
        res_plus = bool(re.search(r'[+＋]', unicodedata.normalize("NFKC", ti)))
        if res_plus != page_plus:
            continue
        v = vol_of(ti, bn)
        if v is None or v in vols:
            continue
        cover = (it.get("largeImageUrl") or "").split("?")[0]
        vols[v] = {"number": v, "asin": None, "isbn13": isbn,
                   "cover_url": cover if cover and "noimage" not in cover else None,
                   "release_date": parse_date(it.get("salesDate"))}
    # 外れ値巻番号を除去(誤parse: 1-10に混じる55等)。 巻数の1.8倍+3 を超える孤立番号を落とす
    if vols:
        thr = max(len(vols) * 1.8 + 3, 12)
        vols = {k: v for k, v in vols.items() if k <= thr}
    report.append((d["slug"], bt, len(vols), sorted(vols.keys())))
    if APPLY and len(vols) >= 2:   # 2巻以上見つかった時のみ再構築(単巻は触らない)
        d["title"] = bt
        for a in d.get("authors", []):
            a["name"] = clean_author(a.get("name", ""))
        d["editions"][0]["volumes"] = [vols[k] for k in sorted(vols)]
        years = [int(str(v["release_date"])[:4]) for v in vols.values() if v.get("release_date")]
        if years:
            d["year_started"] = min(years)
        yaml.safe_dump(d, open(p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    if i % 20 == 0:
        print(f"  {i}/{len(targets)}", flush=True)
    time.sleep(RATE)

multi = [r for r in report if isinstance(r[3], list) and r[2] > 1]
print(f"\n複数巻発見: {len(multi)} / 単巻のまま {len(report)-len(multi)}")
for sl, bt, n, vs in sorted(report, key=lambda x: -(x[2] if isinstance(x[2], int) else 0))[:25]:
    print(f"  {n:2}巻 {bt[:26]:28} {vs if isinstance(vs,list) else vs}")
json.dump([(r[0], r[1], r[2], r[3]) for r in report], open(f"{ROOT}/.cache/ndl71-volumes.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n{'APPLIED' if APPLY else 'DRY-RUN(--applyで適用)'} → .cache/ndl71-volumes.json")
