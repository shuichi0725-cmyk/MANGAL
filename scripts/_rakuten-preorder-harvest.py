#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""楽天予約ハーベスト (= 2026-07-06 設計確定。カレンダー未来データの供給源)

漫画ジャンル(001001)の6サブジャンルを発売日降順でページングし、
「未来〜今日」の予約/新刊を全量取得する。成年は001001ツリー外=構造的に混入しない。

出力: .cache/preorders/preorders-latest.jsonl
  {isbn,title,titleKana,author,authorKana,publisher,salesDate,ym(正規化),unknown_date,
   cover,caption,subgenre,seriesName}
- 仮日付(2030年以降)= unknown_date:true (「発売未定」バケツ=一覧表表示用)
- レート1.1s / resumableでなく毎回フル(未来ゾーンは薄いので数分)
使い方: python scripts/_rakuten-preorder-harvest.py [--max-pages 80]
"""
import json, os, re, sys, time, datetime, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, ".cache", "preorders")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "preorders-latest.jsonl")
MAX_PAGES = int(sys.argv[sys.argv.index("--max-pages") + 1]) if "--max-pages" in sys.argv else 80
SUBGENRES = {"001001001": "少年", "001001002": "少女", "001001003": "青年",
             "001001004": "レディース", "001001006": "文庫", "001001012": "その他"}
RATE = 1.1

env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
ORIGIN = env.get("RAKUTEN_REFERER", "").rstrip("/")

def books(genre, page):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "booksGenreId": genre, "sort": "-releaseDate", "hits": "30", "page": str(page),
         "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0")
    for attempt in range(3):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=25).read())
        except Exception as e:
            if "429" in str(e):
                print("★429→中断"); sys.exit(2)
            time.sleep(RATE * (attempt + 2))
    return {}

def parse_date(s):
    """楽天salesDate → (ym or None, day or None, unknown_date)。2030年以降=仮日付=未定。"""
    m = re.match(r"(\d{4})年(\d{2})月(?:(\d{2})日)?", str(s or ""))
    if not m:
        return None, None, True
    y = int(m.group(1))
    if y >= 2030:
        return None, None, True
    return f"{y:04d}-{m.group(2)}", (int(m.group(3)) if m.group(3) else None), False

today = datetime.date.today()
cutoff = f"{today.year:04d}-{today.month:02d}"
seen = set()
rows = []
for gid, gname in SUBGENRES.items():
    stop = False
    for pg in range(1, MAX_PAGES + 1):
        d = books(gid, pg)
        items = d.get("Items") or []
        if not items:
            break
        past_in_page = 0
        for it in items:
            isbn = str(it.get("isbn") or "")
            if not isbn or isbn in seen:
                continue
            ym, day, unknown = parse_date(it.get("salesDate"))
            if ym and ym < cutoff:
                past_in_page += 1
                continue  # 当月より過去=対象外(だがページ内に混ざるので続行)
            seen.add(isbn)
            img = str(it.get("largeImageUrl") or "")
            rows.append({"isbn": isbn, "title": it.get("title"), "titleKana": it.get("titleKana"),
                         "author": it.get("author"), "authorKana": it.get("authorKana"),
                         "publisher": it.get("publisherName"), "salesDate": it.get("salesDate"),
                         "ym": ym, "day": day, "unknown_date": unknown,
                         "cover": img if img and "noimage" not in img else None,
                         "caption": (it.get("itemCaption") or "")[:500],
                         "seriesName": it.get("seriesName"), "subgenre": gname})
        # このページ全部が過去日付なら未来ゾーン終了
        if past_in_page >= len(items):
            stop = True
        time.sleep(RATE)
        if stop:
            break
    print(f"  {gname}: 累計{len(rows)}件 (p{pg}まで)", flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_unknown = sum(1 for r in rows if r["unknown_date"])
from collections import Counter
dist = Counter(r["ym"] for r in rows if r["ym"])
print(f"完了: {len(rows)}件 (発売未定{n_unknown}) → {OUT}")
print("月分布:", dict(sorted(dist.items())))
