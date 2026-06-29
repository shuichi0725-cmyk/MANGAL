"""集英社 日本の歴史 を NDL(全巻・発行年) + 既存ISBN を統合し、年代版editionに再構築。
発行コード→年代で版を確定、人物日本の歴史(別シリーズ)除外、NDLで欠巻補完、書影は楽天ISBN直引き。"""
import yaml, re, os, json, time, collections, urllib.parse, urllib.request

ROOT = "C:/Users/shuic/code/MANGAL"
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"

CODE_YEAR = {"2440": ("1982年版", "standard"), "2500": ("1982年版", "standard"),
             "1950": ("1992年版", "standard"), "1951": ("1992年版", "standard"), "2441": ("1992年版", "standard"),
             "2390": ("1998年版", "standard"),
             "7461": ("2007年版 漫画版(文庫)", "bunkobon"),
             "2391": ("2016年版 コンパクト", "standard"),
             "2392": ("2021年版", "standard")}
EXCLUDE_CODE = {"2520"}  # 人物日本の歴史=別シリーズ

def code(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    return ib[6:10] if len(ib) == 13 else "?"

# 1) 既存 preview の巻(book data 保持=cover等)
vol_data = {}   # isbn -> volume dict
existing = yaml.safe_load(open(f"{ROOT}/.preview-data/manga/nihonnorekishi.yml", encoding="utf-8"))
for e in existing.get("editions", []):
    for v in e.get("volumes", []):
        ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
        if ib:
            vol_data[ib] = dict(v)

# 2) NDL の巻(欠巻補完)
ndl = json.load(open(f"{ROOT}/.cache/nihonshi-ndl.json", encoding="utf-8"))
for c, recs in ndl.items():
    for vol, r in recs.items():
        ib = r["isbn"]
        if ib not in vol_data:
            vol_data[ib] = {"number": int(vol), "asin": None, "isbn13": ib, "cover_url": None, "release_date": r.get("date") or None}

# 3) 年代版にグループ(コード→年代、 除外コード skip)
byyear = collections.defaultdict(dict)   # (label,type) -> {number: vol}
skipped = collections.Counter()
for ib, v in vol_data.items():
    c = code(ib)
    if c in EXCLUDE_CODE:
        skipped["人物(別シリーズ)"] += 1; continue
    if c not in CODE_YEAR:
        skipped[f"未マップ{c}"] += 1; continue
    label, etype = CODE_YEAR[c]
    n = v.get("number")
    if n is None:
        continue
    key = (label, etype)
    if n not in byyear[key] or (v.get("cover_url") and not byyear[key][n].get("cover_url")):
        byyear[key][n] = v

# 4) 楽天書影(cover無のISBNのみ)
def rk_cover(isbn):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "isbn": isbn, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0")
    try:
        it = (json.loads(urllib.request.urlopen(req, timeout=15).read()).get("Items") or [None])[0]
        if it:
            c = (it.get("largeImageUrl") or "").split("?")[0]
            return c if c and "noimage" not in c else None
    except Exception:
        return None
    return None

ncov = 0
for key, vols in byyear.items():
    for n, v in vols.items():
        if not v.get("cover_url"):
            c = rk_cover(re.sub(r"\D", "", str(v.get("isbn13"))))
            time.sleep(0.4)
            if c:
                v["cover_url"] = c; ncov += 1

# 5) edition組み立て(巻数多い順)
editions = []
for (label, etype), vols in byyear.items():
    vl = [vols[n] for n in sorted(vols)]
    editions.append({"type": etype, "label": f"日本の歴史 {label}", "publisher": "集英社", "volumes": vl})
editions.sort(key=lambda e: -len(e["volumes"]))

print("=== 集英社 日本の歴史 最終構成(NDL補完済) ===")
for e in editions:
    print(f"  [{e['label']}] {e['type']} {len(e['volumes'])}巻 {[v['number'] for v in e['volumes']]}")
print("skip:", dict(skipped), "| 楽天書影追加:", ncov)

existing["editions"] = editions
existing["original_authors"] = [{"name": "児玉幸多", "role": "writer"}]
existing["authors"] = [{"name": "児玉幸多", "role": "writer"}]
existing["source"] = "edu-manga-preview"
yaml.safe_dump(existing, open(f"{ROOT}/.preview-data/manga/nihonnorekishi.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
print("preview 再構築完了")
