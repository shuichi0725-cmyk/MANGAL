"""サイボーグ009 edition-canonical再構築。 楽天harvest→レーベル別に本編4版を確定→edition-override。
著者=石ノ森章太郎(コミカライズ別作シュガー佐藤/土山よしき版は除外)。 spinoff(完結編/VSデビルマン/BGOOPARTS/ムック)は本編edition外。"""
import json, re, os, urllib.parse, urllib.request, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8") if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"

items = []
for pg in range(1, 8):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "title": "サイボーグ009", "booksGenreId": "001001", "outOfStockFlag": "1", "hits": "30", "page": str(pg), "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN+"/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0")
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception:
        break
    its = r.get("Items") or []
    if not its:
        break
    items += its
    time.sleep(1.1)  # 楽天API 1秒1回 厳守

def volnum(t):
    m = re.search(r"009[（(](\d+)", t)
    return int(m.group(1)) if m else None

def cover(it):
    c = (it.get("largeImageUrl") or "").split("?")[0]
    return c if c and "noimage" not in c else None

# 本編4版に分類(ISBN prefix + seriesName)。 spinoff/別作は除外。
ed = {"sc": {}, "gouka": {}, "bunko": {}, "mf": {}}
for it in items:
    t = it.get("title", "")
    if "サイボーグ009" not in t and "サイボーグ００９" not in t:
        continue
    # spinoff/別作を除外
    if any(x in t for x in ["完結編", "VS", "ＶＳ", "BGOOPARTS", "ＢＧＯＯ", "シューガー佐藤", "土山よしき", "00学園", "トリビュート", "USAエディション", "大解剖", "SPECIAL", "クロニクル", "コンプリートブック", "時空間漂流", "その世界", "カラー完全版", "連載再現"]):
        continue
    ib = re.sub(r"\D", "", str(it.get("isbn", "")))
    if len(ib) != 13:
        continue
    n = volnum(t)
    if not n:
        continue
    rec = {"number": n, "isbn13": ib, "cover_url": cover(it), "release_date": (str(it.get("salesDate", "")) or None), "asin": None}
    if ib.startswith("9784253060"):
        ed["sc"].setdefault(n, rec)
    elif ib.startswith("9784253102") or ib.startswith("9784253103"):
        ed["gouka"].setdefault(n, rec)
    elif ib.startswith("978425317"):  # 秋田文庫 4-253-170/172(22,23巻)
        ed["bunko"].setdefault(n, rec)
    elif ib.startswith("9784840104") or ib.startswith("9784840100") or ib.startswith("978488991"):
        ed["mf"].setdefault(n, rec)

def norm_date(r):
    d = r.get("release_date") or ""
    m = re.match(r"(\d{4})年(\d{1,2})?月?(\d{1,2})?", d)
    if m:
        y, mo, da = m.group(1), m.group(2), m.group(3)
        r["release_date"] = y + (f"-{int(mo):02d}" if mo else "") + (f"-{int(da):02d}" if da else "")
    elif not re.match(r"^\d{4}", d):
        r["release_date"] = None
    return r

editions = []
for key, typ, label in [("sc", "standard", "サンデーコミックス"), ("gouka", "aizoban", "豪華版"), ("mf", "kanzenban", "MF完全版"), ("bunko", "bunkobon", "秋田文庫")]:
    vols = [norm_date(ed[key][n]) for n in sorted(ed[key])]
    if vols:
        editions.append({"type": typ, "label": label, "volumes": vols})
        print(f"{label}: {len(vols)}巻 {sorted(ed[key])[:3]}...{sorted(ed[key])[-2:]} 書影{sum(1 for v in vols if v['cover_url'])}/{len(vols)}")

eo = json.load(open(f"{ROOT}/data/seeds/edition-overrides.json", encoding="utf-8"))
eo["cyborg-009"] = {"editions": editions, "authors": [{"name": "石ノ森章太郎", "role": "writer_artist"}]}
json.dump(eo, open(f"{ROOT}/data/seeds/edition-overrides.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("edition-override追加: cyborg-009 (著者→石ノ森章太郎・本編4版)")
