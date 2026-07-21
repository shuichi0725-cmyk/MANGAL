"""NDL欠の巻抜けを ★楽天ブックス題検索 で埋める(楽天はNDLに無い巻も持つ)。
題検索→題一致で全巻(ISBN/巻番/書影/発売日)→FILL seed更新+enrichに書影追記。
usage: python _distill_fill_rakuten.py <slug1> <slug2> ..."""
import sys, re, json, os, time, urllib.request, urllib.parse, yaml, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
RATE = 1.2
env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    if "=" in ln: k, v = ln.split("=", 1); env[k.strip()] = v.strip()
REF = env.get("RAKUTEN_REFERER", "https://github.com/")
from urllib.parse import urlparse
o = urlparse(REF)
def norm(s): return re.sub(r"[\s　・･:：!！?？.,。、\-〜~\[\]()『』「」（）]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def basetitle(t): return re.sub(r"[（(]\s*\d+\s*[)）]\s*$|[.．:：]\s*(vol(ume)?\.?\s*)?\d+.*$|\s*\d+\s*$", "", str(t or ""), flags=re.I).strip()
def vol_of(title):
    m = re.search(r"[（(]\s*(\d+)\s*[)）]\s*$", str(title or "")) or re.search(r"(\d+)\s*$", str(title or ""))
    return int(m.group(1)) if m else 1

def rk_title(title, page=1):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "affiliateId": env.get("RAKUTEN_AFFILIATE", ""),
         "format": "json", "formatVersion": "2", "title": title, "booksGenreId": "001001", "hits": 30, "page": page, "outOfStockFlag": 1}
    u = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p)
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": REF, "Origin": f"{o.scheme}://{o.netloc}", "User-Agent": "M/1"}), timeout=25).read())
        time.sleep(RATE)
        return d.get("Items") or []
    except Exception:
        time.sleep(RATE); return []

slugs = sys.argv[1:]
fillrecs = {json.loads(l)["slug"]: json.loads(l) for l in open(f"{ROOT}/data/seeds/distill-fill-2026.jsonl", encoding="utf-8")}
enrich_add = []
for slug in slugs:
    pf = f"{ROOT}/.preview-data/manga/{slug}.yml"
    if not os.path.exists(pf): print(f"  {slug}: page無"); continue
    d = yaml.safe_load(open(pf, encoding="utf-8"))
    bt = basetitle(d.get("title", ""))
    nt = norm(bt)
    items = rk_title(bt) + rk_title(bt, 2)
    seen = {}
    for it in items:
        if norm(basetitle(it.get("title", ""))) != nt: continue  # ★題一致のみ
        isbn = re.sub(r"\D", "", str(it.get("isbn", "")))
        if len(isbn) != 13: continue
        n = vol_of(it.get("title", ""))
        sd = it.get("salesDate", "")
        m = re.search(r"(\d{4}).*?(\d{1,2})月", sd)
        rd = f"{m.group(1)}-{int(m.group(2)):02d}" if m else (re.match(r"(\d{4})", sd).group(1) if re.match(r"(\d{4})", sd) else None)
        cov = (it.get("largeImageUrl") or "").split("?")[0]
        if n not in seen:
            seen[n] = {"number": n, "isbn13": isbn, "release_date": rd}
            if cov and "noimage" not in cov: enrich_add.append({"isbn": isbn, "cover": cov, "caption": it.get("itemCaption", ""), "publisher": it.get("publisherName", ""), "rk_title": it.get("title", "")})
    if not seen: print(f"  {slug}: 楽天題検索でヒット無({bt[:16]})"); continue
    # ★既存FILL(NDL等)と和集合(巻の取りこぼし最大化)
    merged = {v["number"]: v for v in fillrecs.get(slug, {}).get("volumes", [])}
    for n, v in seen.items():
        if n not in merged: merged[n] = v
    vols = sorted(merged.values(), key=lambda v: v["number"])
    fillrecs[slug] = {"slug": slug, "base_title": d.get("title"), "author": ",".join(a.get("name", "") for a in d.get("authors", [])), "volumes": vols, "n_found": len(vols), "src": "rakuten"}
    print(f"  {slug}: 楽天で {len(vols)}巻 (巻番{[v['number'] for v in vols]})")
with open(f"{ROOT}/data/seeds/distill-fill-2026.jsonl", "w", encoding="utf-8") as f:
    for r in fillrecs.values(): f.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(f"{ROOT}/data/seeds/distill-enrich-2026.jsonl", "a", encoding="utf-8") as f:
    for r in enrich_add: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"FILL更新 / enrich書影追記 {len(enrich_add)}")
