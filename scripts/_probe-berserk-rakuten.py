"""[調査only] 楽天BooksBook APIで ベルセルク vol1/2/43 の取得可否を確認。データ変更なし。"""
import os, json, time, urllib.parse, urllib.request

# .env.local 読み込み(コミットしない秘密)
env = {}
for fn in (".env.local", ".env"):
    if os.path.exists(fn):
        for ln in open(fn, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))

app = env.get("RAKUTEN_APP_ID"); ak = env.get("RAKUTEN_ACCESS_KEY")
ref = env.get("RAKUTEN_REFERER", "http://localhost/")
origin = "http://localhost"
try:
    u = urllib.parse.urlparse(ref); origin = f"{u.scheme}://{u.netloc}"
except Exception:
    pass
EP = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"

def call(params):
    q = {"applicationId": app, "accessKey": ak, "format": "json", "formatVersion": "2",
         "booksGenreId": "001001", "hits": "30"}
    q.update(params)
    url = EP + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={
        "Referer": ref, "Origin": origin, "User-Agent": "MANGAL-DataFetch/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def show(label, params):
    try:
        d = call(params)
    except Exception as e:
        print(f"[{label}] ERROR {e}"); return
    items = d.get("Items") or []
    print(f"[{label}] count={d.get('count')} 返り={len(items)}")
    for it in items[:8]:
        o = it.get("Item", it)
        img = o.get("largeImageUrl") or ""
        st = "NOIMG" if (not img or "noimage" in img) else "IMG"
        print(f"    {o.get('isbn')} | {st} | {o.get('title')}")
    time.sleep(1)

print("app set:", bool(app), "/ accessKey set:", bool(ak), "/ referer:", ref)
show("ISBN vol1 9784592135746", {"isbn": "9784592135746"})
show("ISBN vol2 9784592135753", {"isbn": "9784592135753"})
show("ISBN vol43 9784592106401", {"isbn": "9784592106401"})
show("title=ベルセルク (page1, 出版社=白泉社想定)", {"title": "ベルセルク"})
