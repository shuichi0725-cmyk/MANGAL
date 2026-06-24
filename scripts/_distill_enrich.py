"""蒸留enrich(楽天): in-scope新刊の 書影+caption+アフィリンク+出版社 を楽天で取得。
叩き速度=楽天規定 1.2秒/req。resumable(取得済skip)。出力: .cache/distill-enrich-2026.jsonl"""
import csv, json, os, re, time, urllib.request, urllib.parse
ROOT = "C:/Users/shuic/code/MANGAL"
OUT = f"{ROOT}/.cache/distill-enrich-2026.jsonl"
RATE = 1.2  # ★楽天Books API 1req/秒 規定
env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    if "=" in ln: k, v = ln.split("=", 1); env[k.strip()] = v.strip()
REF = env.get("RAKUTEN_REFERER", "https://github.com/")
from urllib.parse import urlparse
o = urlparse(REF)

done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["isbn"])
        except: pass
# in-scope ISBN(manifest)
todo = [r["isbn"] for r in csv.DictReader(open(f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in" and r["isbn"] not in done]
print(f"in-scope未取得: {len(todo)}", flush=True)

def rk(isbn):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE", ""), "format": "json", "formatVersion": "2",
         "isbn": isbn, "hits": 1, "outOfStockFlag": 1}
    u = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p)
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": REF, "Origin": f"{o.scheme}://{o.netloc}", "User-Agent": "M/0.1"}), timeout=25).read())
        its = d.get("Items") or []
        if its:
            it = its[0]
            return {"cover": (it.get("largeImageUrl") or "").split("?")[0], "caption": it.get("itemCaption", ""),
                    "affiliate": it.get("affiliateUrl", ""), "publisher": it.get("publisherName", ""), "rk_title": it.get("title", "")}
    except Exception as e: return {"err": str(e)[:40]}
    return {}

fo = open(OUT, "a", encoding="utf-8"); n = 0
for isbn in todo:
    rec = {"isbn": isbn, **rk(isbn)}
    fo.write(json.dumps(rec, ensure_ascii=False) + "\n"); fo.flush(); n += 1
    if n % 50 == 0: print(f"  {n}/{len(todo)}", flush=True)
    time.sleep(RATE)
fo.close()
recs = [json.loads(l) for l in open(OUT, encoding="utf-8")]
print(f"完了: {len(recs)}件 / 書影{sum(1 for r in recs if r.get('cover'))} / caption{sum(1 for r in recs if r.get('caption'))}")
