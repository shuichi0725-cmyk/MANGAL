"""教育系の年代版混入を汎用的に是正(日本の歴史の横展開)。
slug指定→NDL title検索で全巻取得→出版社prefix絞り→ISBN発行コード×NDL発行年で年代版に分離→欠巻補完→楽天書影。
dry-run=結果表示 / --apply=preview反映。 慎重: backup・別シリーズ除外・人手確認前提。"""
import sys, yaml, re, os, json, time, collections, urllib.parse, urllib.request, html, unicodedata

ROOT = "C:/Users/shuic/code/MANGAL"
SLUG = sys.argv[1] if len(sys.argv) > 1 else None
APPLY = "--apply" in sys.argv
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"
SRU = "https://ndlsearch.ndl.go.jp/api/sru"

def reg(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    if not ib.startswith("9784") or len(ib) != 13:
        return None
    b = ib[4:12]; n = int(b[:2])
    return b[:2] if n <= 19 else b[:3] if n <= 69 else b[:4] if n <= 84 else b[:5] if n <= 89 else b[:6] if n <= 94 else b[:7]

def codeof(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    return ib[6:10] if len(ib) == 13 else None

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

d = yaml.safe_load(open(f"{ROOT}/data/manga.v2/{SLUG}.yml", encoding="utf-8"))
title = d["title"]
base = norm(title)
# 既存巻の majority registrant = 正規出版社
regs = collections.Counter(reg(v.get("isbn13")) for e in d.get("editions", []) for v in e.get("volumes", []) if reg(v.get("isbn13")))
PUB = regs.most_common(1)[0][0] if regs else None
print(f"■ {SLUG} | {title} | 正規出版社prefix={PUB}")

# NDL title検索
def fetch(start):
    q = {"operation": "searchRetrieve", "query": f'title="{title}"', "recordSchema": "dcndl", "maximumRecords": "100", "startRecord": str(start)}
    req = urllib.request.Request(SRU + "?" + urllib.parse.urlencode(q)); req.add_header("User-Agent", "Mozilla/5.0")
    return html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))

records = []
start = 1
for _ in range(12):
    xml = fetch(start)
    recs = re.split(r"<recordData", xml)[1:]
    if not recs:
        break
    for r in recs:
        isbns = [re.sub(r"\D", "", i) for i in re.findall(r"(97[89][\d\-]{9,16})", r)]
        isbns = [i for i in isbns if len(i) == 13 and reg(i) == PUB]   # ★正規出版社のみ
        if not isbns:
            continue
        ib = isbns[0]
        vol = None
        mv = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)</rdf:value>", r, re.S) or re.search(r"<dcndl:volume>\s*([^<]+?)\s*</dcndl:volume>", r)
        if mv:
            mn = re.search(r"\d+", mv.group(1)); vol = int(mn.group()) if mn else None
        date = ""
        md = re.search(r"<dcterms:(?:issued|date)[^>]*>([^<]+)<", r) or re.search(r"<dc:date>([^<]+)<", r)
        if md:
            m2 = re.search(r"([0-9]{4})(?:[-.]([0-9]{1,2}))?", unicodedata.normalize("NFKC", md.group(1)))
            if m2:
                date = m2.group(1) + (f"-{int(m2.group(2)):02d}" if m2.group(2) else "")
        rt = ""
        mt = re.search(r"<dc:title>.*?<rdf:value>([^<]+)</rdf:value>", r, re.S) or re.search(r"<dc:title>([^<]+)</dc:title>", r)
        if mt:
            rt = re.sub(r"<.*?>", "", mt.group(1)).strip()
        # ★別シリーズ除外: 実題名に base が含まれない
        if base[:6] not in norm(rt):
            continue
        records.append({"isbn": ib, "vol": vol, "date": date, "title": rt})
    if len(recs) < 100:
        break
    start += len(recs); time.sleep(1.2)

# 既存巻も統合(cover保持)
vol_data = {}
for e in d.get("editions", []):
    for v in e.get("volumes", []):
        ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
        if ib:
            vol_data[ib] = dict(v)
for r in records:
    if r["isbn"] not in vol_data and r["vol"]:
        vol_data[r["isbn"]] = {"number": r["vol"], "asin": None, "isbn13": r["isbn"], "cover_url": None, "release_date": r["date"] or None}

# コード→代表年(NDL+既存の日付)
code_years = collections.defaultdict(list)
for ib, v in vol_data.items():
    c = codeof(ib)
    y = re.match(r"(\d{4})", str(v.get("release_date") or ""))
    if c and y:
        code_years[c].append(int(y.group(1)))
code_year = {c: collections.Counter(ys).most_common(1)[0][0] for c, ys in code_years.items()}

# 年代でグループ(同年コードは合流)
byyear = collections.defaultdict(dict)
for ib, v in vol_data.items():
    c = codeof(ib); n = v.get("number")
    if c is None or n is None:
        continue
    yr = code_year.get(c)
    if yr is None:
        continue
    if n not in byyear[yr] or (v.get("cover_url") and not byyear[yr][n].get("cover_url")):
        byyear[yr][n] = v

print(f"NDL取得 {len(records)}件(正規出版社・別シリーズ除外後) / 全巻 {len(vol_data)}")
print("=== 年代版分離結果 ===")
for yr in sorted(byyear):
    print(f"  {yr}年版: {len(byyear[yr])}巻 {sorted(byyear[yr])}")

if APPLY:
    def rk_cover(isbn):
        p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "isbn": isbn, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
        req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
        req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0")
        try:
            it = (json.loads(urllib.request.urlopen(req, timeout=15).read()).get("Items") or [None])[0]
            if it:
                c = (it.get("largeImageUrl") or "").split("?")[0]
                return c if c and "noimage" not in c else None
        except Exception:
            return None
    ncov = 0
    for yr, vols in byyear.items():
        for n, v in vols.items():
            if not v.get("cover_url"):
                c = rk_cover(re.sub(r"\D", "", str(v.get("isbn13")))); time.sleep(0.4)
                if c:
                    v["cover_url"] = c; ncov += 1
    editions = []
    for yr in sorted(byyear, reverse=True):
        vl = [byyear[yr][n] for n in sorted(byyear[yr])]
        editions.append({"type": "standard", "label": f"{title} {yr}年版", "publisher": d.get("publisher"), "volumes": vl})
    editions.sort(key=lambda e: -len(e["volumes"]))
    d["editions"] = editions
    d["source"] = "edu-manga-preview"
    os.makedirs(f"{ROOT}/.cache/edu-disentangle-bak", exist_ok=True)
    import shutil
    pp = f"{ROOT}/.preview-data/manga/{SLUG}.yml"
    if os.path.exists(pp):
        shutil.copy(pp, f"{ROOT}/.cache/edu-disentangle-bak/{SLUG}.yml.bak")
    yaml.safe_dump(d, open(pp, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    print(f"APPLIED: {len(editions)}年代版 / 楽天書影+{ncov} → preview")
