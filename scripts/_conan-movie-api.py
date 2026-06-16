"""[調査] コナン映画クラスタの全ISBNを楽天API直引きで取得→title/author/dateを得て分類。
キャッシュ命中分も含め全78 ISBNを「フィルムコミック(drop)/漫画版(keep)/その他」に一次分類。
楽天APIは収穫完走後=空き。1req/秒。結果は .cache/conan-movie-class.json。本番未変更。"""
import json, sqlite3, time, re, urllib.parse, urllib.request, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
env = {}
for ln in open(".env.local", encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
ref = env.get("RAKUTEN_REFERER", "http://localhost/")
u = urllib.parse.urlparse(ref)
origin = f"{u.scheme}://{u.netloc}"
EP = "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"

con = sqlite3.connect(".cache/db-v2.sqlite")
rows = con.execute("""select s.title,
  (select count(*) from volumes v join editions e on v.edition_id=e.id where e.series_id=s.id) nv, s.id
  from series s where (s.title like '名探偵コナン %' or s.title like '名探偵コナン　%')""").fetchall()
movies = {}
for title, nv, sid in rows:
    if nv > 6:
        continue
    sub = title.replace("名探偵コナン", "").strip()
    if not sub:
        continue
    vols = con.execute("select v.number,v.release_date,v.isbn13 from volumes v join editions e on v.edition_id=e.id where e.series_id=? order by v.number", (sid,)).fetchall()
    movies.setdefault(sub, [])
    for n, rd, i in vols:
        if i:
            movies[sub].append((n, str(rd or ""), str(i)))

# 既存キャッシュ
cache = {}
import os
if os.path.exists(".cache/rakuten-isbn.jsonl"):
    with open(".cache/rakuten-isbn.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if '"isbn"' not in line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            i = str(r.get("isbn") or "")
            if i and i not in cache:
                it = r.get("item") or {}
                if it:
                    cache[i] = {"title": it.get("title", ""), "author": it.get("author", ""), "date": it.get("salesDate", "")}


def api(isbn):
    q = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "isbn": isbn, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request(EP + "?" + urllib.parse.urlencode(q),
                                 headers={"Referer": ref, "Origin": origin, "User-Agent": "MANGAL/0.1", "Accept": "application/json"})
    for a in range(4):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=20).read())
            its = d.get("Items", [])
            o = (its[0].get("Item", its[0]) if its else {})
            return {"title": o.get("title", ""), "author": o.get("author", ""), "date": o.get("salesDate", "")}
        except Exception as e:
            if "429" in str(e) and a < 3:
                time.sleep(6 + a * 6); continue
            return None


def classify(t):
    t = t or ""
    if "フィルムコミック" in t or "フィルムブック" in t:
        return "FILM"
    if re.search(r"[（(]?(上|下|完全版)[）)]?\s*$", t):
        return "FILM?"
    if re.search(r"(VOLUME|Volume)\s*\d", t) or re.search(r"\d+\s*$", t):
        return "MANGA?"
    return "?"


all_isbns = [(sub, n, rd, i) for sub, vs in movies.items() for (n, rd, i) in vs]
need = [i for _, _, _, i in all_isbns if i not in cache]
print(f"映画{len(movies)} / ISBN {len(all_isbns)} / API要 {len(need)}", flush=True)
done = 0
for i in need:
    r = api(i)
    if r:
        cache[i] = r
    done += 1
    if done % 20 == 0:
        print(f"  API {done}/{len(need)}", flush=True)
    time.sleep(1.1)

out = {}
for sub, n, rd, i in all_isbns:
    c = cache.get(i, {})
    out.setdefault(sub, []).append({"num": n, "our_date": rd, "isbn": i,
                                    "rk_title": c.get("title", ""), "author": c.get("author", ""),
                                    "rk_date": c.get("date", ""), "cls": classify(c.get("title", ""))})
json.dump(out, open(".cache/conan-movie-class.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("\n=== 分類(楽天題ベース一次) ===")
for sub in sorted(out):
    tags = [e["cls"] for e in out[sub]]
    print(f"■ {sub}  [{'/'.join(sorted(set(tags)))}]")
    for e in out[sub]:
        print(f"   #{e['num']} {e['isbn']} {e['cls']:<6} | {e['rk_title'][:34]} | {e['author'][:16]} | {e['rk_date']}")
