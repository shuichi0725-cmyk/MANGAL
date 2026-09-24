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
使い方: python scripts/_rakuten-preorder-harvest.py [--max-pages 100] [--out PATH]
★取りこぼし警告(2026-09-24): 楽天の検索は 1クエリ 30件×**最大100頁=3,000件**まで(公式ドキュメント)。
  発売日降順でたどるので、頁の上限で打ち切られると**当月〜近い未来の新刊(列の後ろ側)が黙って落ちる**。
  しかも毎回同じ所で切れるので、その本は発売月を過ぎて対象外になるまで一度も拾われない(=恒久的な取りこぼし)。
  2026-09-19 実測で「その他」2,052件 = 旧上限80頁(2,400件)の85%。→ 既定を100頁(API上限)に上げ、
  各ジャンルが「過去日付の頁」まで届いたかを判定して、届かなかったら最後に★警告を出す。
  結果は .cache/preorders/harvest-status.json にも残す。警告が出たらジャンルを細分して取る(下位ジャンル/出版社)。
"""
import json, os, re, sys, time, datetime, urllib.request, urllib.parse, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, ".cache", "preorders")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
       else os.path.join(OUT_DIR, "preorders-latest.jsonl"))
API_MAX_PAGES = 100   # 楽天 BooksBook/Search の page 上限(1〜100)= 1クエリ最大3,000件
WARN_RATIO = 0.85     # 上限のこの割合まで頁を使ったら「余裕が無い」と事前に知らせる
MAX_PAGES = min(API_MAX_PAGES, int(sys.argv[sys.argv.index("--max-pages") + 1])
                if "--max-pages" in sys.argv else API_MAX_PAGES)
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
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:  # ★厳密判定(偽429対策2026-08-03: 文字列マッチはJSON崩れの「column 429」を誤検知)
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
status = {}
for gid, gname in SUBGENRES.items():
    stop = False
    ended = "cap"          # past=過去日付まで到達(完走) / end=検索結果の最後まで読んだ / cap=頁上限で打ち切り
    api_pages = None
    n_before = len(rows)
    for pg in range(1, MAX_PAGES + 1):
        d = books(gid, pg)
        items = d.get("Items") or []
        if not items:
            ended = "end"
            break
        api_pages = d.get("pageCount") or api_pages
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
            ended = "past"
            break
        if api_pages and pg >= int(api_pages):
            # 検索結果の最終頁まで読んだ。ただし API が100頁で頭打ちなら、その先(3,001件目〜)は届かない
            ended = "cap" if int(api_pages) >= API_MAX_PAGES else "end"
            break
    limit = min(MAX_PAGES, API_MAX_PAGES)
    status[gname] = {"genre": gid, "pages": pg, "limit": limit, "api_pageCount": api_pages,
                     "kept": len(rows) - n_before, "ended": ended,
                     "truncated": ended == "cap", "near_limit": ended != "cap" and pg >= WARN_RATIO * limit}
    print(f"  {gname}: 累計{len(rows)}件 (p{pg}まで・{ended})", flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_unknown = sum(1 for r in rows if r["unknown_date"])
from collections import Counter
dist = Counter(r["ym"] for r in rows if r["ym"])
print(f"完了: {len(rows)}件 (発売未定{n_unknown}) → {OUT}")
print("月分布:", dict(sorted(dist.items())))

# ★取りこぼし検査(最後に出す=読み飛ばされないように)
json.dump({"at": datetime.datetime.now().isoformat(timespec="seconds"), "max_pages": MAX_PAGES, "genres": status},
          open(os.path.join(os.path.dirname(OUT) or ".", "harvest-status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
trunc = [g for g, s in status.items() if s["truncated"]]
near = [g for g, s in status.items() if s["near_limit"]]
if trunc:
    print("\n★★ 取りこぼし警告: 頁の上限で打ち切られ、当月〜近い未来の新刊が取れていないジャンルがある")
    for g in trunc:
        s = status[g]
        print(f"   ★ {g}({s['genre']}): {s['pages']}/{s['limit']}頁で打ち切り・過去日付まで届かず(API pageCount={s['api_pageCount']})")
    print("   → --max-pages を上げる(上限100)か、100頁でも足りなければジャンルを細分して取る。このまま進めると取りこぼす")
elif near:
    print("\n★ 取りこぼし注意: 上限まで余裕が少ないジャンル(今回は取り切れている)")
    for g in near:
        s = status[g]
        print(f"   ・{g}: {s['pages']}/{s['limit']}頁 = {s['pages'] * 100 // s['limit']}%")
else:
    worst = max(status.items(), key=lambda kv: kv[1]["pages"] / kv[1]["limit"]) if status else None
    if worst:
        print(f"\n取りこぼし検査: OK 全ジャンル過去日付まで到達(最大 {worst[0]} {worst[1]['pages']}/{worst[1]['limit']}頁)")
