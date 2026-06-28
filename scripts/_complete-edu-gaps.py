"""教育系の歯抜け作を出版社prefix制約でRakuten補完(同prefixのみ追加=過剰統合防止)。
generic題なので prefix一致 + 題前方一致 + EXCL で厳格filter。 preview反映。"""
import json, yaml, re, os, time, urllib.parse, urllib.request, unicodedata

ROOT = "C:/Users/shuic/code/MANGAL"
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"

def reg(i):
    if not i.startswith("9784") or len(i) != 13:
        return None
    b = i[4:12]; n = int(b[:2])
    return b[:2] if n <= 19 else b[:3] if n <= 69 else b[:4] if n <= 84 else b[:5] if n <= 89 else b[:6] if n <= 94 else b[:7]

def norm(s):
    return re.sub(r"[\s　・,.。、:：!！?？]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

EXCL = re.compile(r"ガイド|セット|事典|index|別巻|総集|画集|データ")

def search(title):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "title": title,
         "outOfStockFlag": "1", "hits": "30", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0")
    return json.loads(urllib.request.urlopen(req, timeout=25).read()).get("Items") or []

def volnum(t):
    tt = unicodedata.normalize("NFKC", str(t))
    m = re.search(r"第\s*(\d+)\s*巻", tt) or re.search(r"[(（]\s*(\d+)\s*[)）]", tt) or re.search(r"(\d+)\s*$", tt)
    return int(m.group(1)) if m else None

slugs = json.load(open(f"{ROOT}/.cache/edu-gap-slugs.json", encoding="utf-8"))
for sl in slugs:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    d = yaml.safe_load(open(p, encoding="utf-8"))
    ed = d["editions"][0]
    cur_isbns = {re.sub(r"\D", "", str(v.get("isbn13") or "")) for v in ed["volumes"]}
    cur_nums = {v["number"] for v in ed["volumes"]}
    pref = None
    for ib in cur_isbns:
        pref = reg(ib)
        if pref:
            break
    base = norm(re.sub(r"\s*\d+\s*$", "", d["title"]))
    try:
        items = search(d["title"])
    except Exception:
        print(sl, "search err"); continue
    time.sleep(1.2)
    added = 0
    for it in items:
        ti = it.get("title", ""); ib = re.sub(r"\D", "", str(it.get("isbn") or ""))
        if len(ib) != 13 or reg(ib) != pref:   # ★同出版社のみ
            continue
        if EXCL.search(ti) or base not in norm(ti):
            continue
        vn = volnum(ti)
        if vn is None or vn in cur_nums or ib in cur_isbns:
            continue
        cov = (it.get("largeImageUrl") or "").split("?")[0]
        sd = str(it.get("salesDate") or ""); m = re.match(r"(\d{4})年(\d{1,2})月", sd)
        ed["volumes"].append({"number": vn, "asin": None, "isbn13": ib,
                              "cover_url": cov if cov and "noimage" not in cov else None,
                              "release_date": f"{m.group(1)}-{int(m.group(2)):02d}" if m else None})
        cur_nums.add(vn); cur_isbns.add(ib); added += 1
    ed["volumes"].sort(key=lambda v: v["number"])
    d["source"] = "edu-manga-preview"
    yaml.safe_dump(d, open(f"{ROOT}/.preview-data/manga/{sl}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    print(f"{d['title'][:24]:26} +{added} → {sorted(v['number'] for v in ed['volumes'])}")
