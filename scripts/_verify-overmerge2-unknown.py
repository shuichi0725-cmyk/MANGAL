"""(2)残74件(harvest未収録の上限超え巻)をRakuten直接照会し実題名で別作混入か確定。"""
import json, re, os, time, unicodedata, urllib.parse, urllib.request, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8")
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

def rk(isbn):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "isbn": isbn,
         "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0")
    try:
        return (json.loads(urllib.request.urlopen(req, timeout=20).read()).get("Items") or [None])[0]
    except Exception:
        return None

above = json.load(open(f"{ROOT}/.cache/overmerge2-above.json", encoding="utf-8"))
unk = [x for x in above if x[6] == "?"]
print(f"未照合 {len(unk)} 件を照会", flush=True)
bad = []
for sl, t, n, ib, rt, ra, vd in unk:
    it = rk(ib); time.sleep(1.1)
    if not it:
        print(f"  [楽天無] {t} vol{n} (isbn{ib})"); continue
    real = it.get("title", ""); rau = it.get("author", "")
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    d = yaml.safe_load(open(p, encoding="utf-8"))
    wt = norm(d.get("title", "")); wau = [norm(a.get("name")) for a in (d.get("authors") or []) + (d.get("original_authors") or []) if a.get("name")]
    same = (wt in norm(real)) or (rau and any(wa and wa in norm(rau) for wa in wau))
    mark = "同一作" if same else "★別作混入"
    if not same:
        bad.append((sl, t, n, ib, real, rau))
    print(f"  [{mark}] {t} vol{n} → 実題[{real[:28]}] 著[{rau[:16]}]")
print(f"\n★別作混入(確定): {len(bad)}")
json.dump(bad, open(f"{ROOT}/.cache/overmerge2-unknown-bad.json", "w", encoding="utf-8"), ensure_ascii=False)
