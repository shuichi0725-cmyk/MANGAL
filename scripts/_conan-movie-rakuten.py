"""[調査] コナン映画クラスタの全ISBNを楽天キャッシュ(rakuten-isbn.jsonl)で引き、
題/著者/発売日からフィルムコミック vs 漫画版 を一次分類。Wikipedia突合の土台。本番未変更。"""
import json, glob, yaml, sqlite3, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 我々のコナン映画クラスタ(db-v2)とISBN
con = sqlite3.connect(".cache/db-v2.sqlite")
rows = con.execute("""select s.id, s.title,
  (select count(*) from volumes v join editions e on v.edition_id=e.id where e.series_id=s.id) nv
  from series s where (s.title like '名探偵コナン %' or s.title like '名探偵コナン　%')""").fetchall()
movies = {}
want = set()
for sid, title, nv in rows:
    if nv > 6:
        continue
    sub = title.replace("名探偵コナン", "").strip()
    if not sub:
        continue
    vols = con.execute("""select v.number,v.release_date,v.isbn13 from volumes v join editions e on v.edition_id=e.id
        where e.series_id=? order by v.number""", (sid,)).fetchall()
    isbns = [str(i) for n, rd, i in vols if i]
    movies.setdefault(sub, []).extend([(n, str(rd or ""), str(i or "")) for n, rd, i in vols])
    want.update(isbns)

# 楽天キャッシュ
cache = {}
with open(".cache/rakuten-isbn.jsonl", encoding="utf-8") as fh:
    for line in fh:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        i = str(r.get("isbn") or "")
        if i in want and i not in cache:
            it = r.get("item") or {}
            cache[i] = {"title": it.get("title", ""), "author": it.get("author", ""),
                        "date": it.get("salesDate", "")}


def classify(rk_title, our_date):
    t = rk_title or ""
    if "フィルムコミック" in t or "フィルムブック" in t:
        return "film(題に明記)"
    if re.search(r"(上巻|下巻|完全版|上\b|下\b)", t) and "VOLUME" not in t.upper():
        return "film?(上下/完全版)"
    if re.search(r"(VOLUME|Volume|\d+$)", t):
        return "manga?(番号付)"
    return "?"


print(f"コナン映画クラスタ {len(movies)} / 対象ISBN {len(want)} / 楽天キャッシュ命中 {len(cache)}")
for sub in sorted(movies):
    print(f"\n■ {sub}")
    for n, rd, isbn in movies[sub]:
        c = cache.get(isbn)
        if c:
            print(f"   #{n} {rd} {isbn} | 楽天題={c['title'][:30]} | 著={c['author'][:18]} | 楽天日={c['date']} | 一次={classify(c['title'], rd)}")
        else:
            print(f"   #{n} {rd} {isbn} | 楽天キャッシュ無し")
