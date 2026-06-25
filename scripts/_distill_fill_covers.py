"""fill earlier volumes の書影を楽天取得→distill-enrich-2026.jsonl に追記。"""
import json, os, time, urllib.request, urllib.parse
ROOT = "C:/Users/shuic/code/MANGAL"
OUT = f"{ROOT}/data/seeds/distill-enrich-2026.jsonl"
RATE = 1.2
env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    if "=" in ln: k, v = ln.split("=", 1); env[k.strip()] = v.strip()
REF = env.get("RAKUTEN_REFERER", "https://github.com/")
from urllib.parse import urlparse
o = urlparse(REF)
todo = json.load(open(f"{ROOT}/.cache/fill-isbns-todo.json"))
def rk(isbn):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "affiliateId": env.get("RAKUTEN_AFFILIATE", ""), "format": "json", "formatVersion": "2",
         "isbn": isbn, "hits": 1, "outOfStockFlag": 1}
    u = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p)
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": REF, "Origin": f"{o.scheme}://{o.netloc}", "User-Agent": "M/1"}), timeout=25).read())
        its = d.get("Items") or []
        if its:
            it = its[0]
            return {"cover": (it.get("largeImageUrl") or "").split("?")[0], "caption": it.get("itemCaption", ""),
                    "affiliate": it.get("affiliateUrl", ""), "publisher": it.get("publisherName", ""), "rk_title": it.get("title", "")}
    except Exception as e: return {"err": str(e)[:40]}
    return {}
fo = open(OUT, "a", encoding="utf-8"); n = 0
for isbn in todo:
    fo.write(json.dumps({"isbn": isbn, **rk(isbn)}, ensure_ascii=False) + "\n"); fo.flush(); n += 1
    if n % 30 == 0: print(f"  {n}/{len(todo)}", flush=True)
    time.sleep(RATE)
fo.close()
print(f"完了: {n}件追記")
