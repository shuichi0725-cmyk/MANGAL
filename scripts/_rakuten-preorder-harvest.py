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

★取りこぼし対策(2026-09-24): 楽天の検索は 1クエリ 30件×**最大100頁=3,000件**まで(公式ドキュメント)。
  発売日降順でたどるので、頁の上限で打ち切られると**当月〜近い未来の新刊(列の後ろ側)が黙って落ちる**。
  しかも毎回同じ所で切れるので、その本は発売月を過ぎて対象外になるまで一度も拾われない(=恒久的な取りこぼし)。
  → **上限で打ち切られたクエリだけ、自動で細かく分けて取り直す**(ふだんの呼び出し数は増えない):
    ① 子ジャンルに分ける(BooksGenre/Search。青年=58・少女=24・少年=12。★「その他」には子が無い)
    ② 判型(size 1〜10)で分ける = ほぼ漏れない(★判型の無い本が少し在る: 実測 その他 167,020中2,497 / 青年 112,768中540。
       新刊は判型付きがほとんど=列の後ろ[当月]の漏れはまず無い)
    ③ 在庫状況(availability)で分ける = 予約受付中(5)/在庫あり(1)/…
       ★**漏れる**: 品切れの本は availability が空で、どの値でも引けない(7以上の値はAPIが受け付けない)。
       2026-09-24 実測: 在庫状況だけで分けたら その他 2,088件中7件(全部 当月発売済みの品切れ=特装版等)が落ちた。
       → 最後の手段。使ったら ★注意 を出す(発売前=予約受付中の日次で取れていれば実害なし)。
    分けた先の総ヒット数の合計が親に届くかを毎回検算し、届かなければ次の分け方でも取り直す
    (子ジャンルに属さず親に直接ぶら下がる本があっても落とさない)。分けた先がまた上限にかかれば同じ手順を繰り返す(深さ4まで)。
    全部やっても上限にかかるクエリが残った時と、API が3回失敗した時だけ ★★警告。
  ★レートは _get() の中で守る(呼び出し側の sleep 任せだと 0件即breakの経路で連打→429で全停止。2026-09-24 試験で実踏)。
  ★ドキュメント外の在庫状況値(実測 11 = 発売日3099年の仮日付品)は列の先頭(最も未来)に並ぶので、
    分ける前の親クエリの100頁で既に取れている。
  結果は harvest-status.json(出力と同じ場所)に残す。
"""
import json, os, re, sys, time, datetime, urllib.request, urllib.parse, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, ".cache", "preorders")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
       else os.path.join(OUT_DIR, "preorders-latest.jsonl"))
API_MAX_PAGES = 100   # 楽天 BooksBook/Search の page 上限(1〜100)= 1クエリ最大3,000件
WARN_RATIO = 0.85     # 上限のこの割合まで頁を使ったら「自動細分の発動が近い」と知らせる
MAX_DEPTH = 4         # 自動細分の深さ上限(子ジャンル→判型→在庫状況 の各段で1つ深くなる)
MAX_PAGES = min(API_MAX_PAGES, int(sys.argv[sys.argv.index("--max-pages") + 1])
                if "--max-pages" in sys.argv else API_MAX_PAGES)
SUBGENRES = {"001001001": "少年", "001001002": "少女", "001001003": "青年",
             "001001004": "レディース", "001001006": "文庫", "001001012": "その他"}
AVAILABILITY = {5: "予約受付中", 1: "在庫あり", 2: "3-7日", 3: "3-9日", 4: "お取り寄せ", 6: "メーカー在庫確認"}
SIZES = {9: "コミック", 1: "単行本", 2: "文庫", 3: "新書", 4: "全集・双書", 5: "事典・辞典",
         6: "図鑑", 7: "絵本", 8: "CD等", 10: "ムックその他"}
RATE = 1.1

env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
ORIGIN = env.get("RAKUTEN_REFERER", "").rstrip("/")
N_CALLS = 0
_LAST_CALL = 0.0


def _get(path, params):
    """★レートはここで守る(前回の呼び出しから RATE 秒空ける)。呼び出し側の sleep に頼ると、
    0件で即 break する経路などで連打になり 429 で全体が止まる(2026-09-24 自動細分の試験で実踏)。
    return 応答dict / 3回失敗したら None(★「0件」と区別する。失敗を「結果の終わり」と読むと黙って落ちる)"""
    global N_CALLS, _LAST_CALL
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "format": "json", "formatVersion": "2", **params}
    req = urllib.request.Request(f"https://openapi.rakuten.co.jp/services/api/{path}?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0")
    for attempt in range(3):
        wait = _LAST_CALL + RATE * (1 if attempt == 0 else attempt + 2) - time.time()
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL = time.time()
        try:
            N_CALLS += 1
            return json.loads(urllib.request.urlopen(req, timeout=25).read())
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:  # ★厳密判定(偽429対策2026-08-03: 文字列マッチはJSON崩れの「column 429」を誤検知)
                print("★429→中断"); sys.exit(2)
            _LAST_CALL = time.time()
    return None


def books(query, page):
    """query = {booksGenreId, [availability], [size]}。発売日降順・在庫切れも含む。"""
    return _get("BooksBook/Search/20170404",
                {**query, "sort": "-releaseDate", "hits": "30", "page": str(page), "outOfStockFlag": "1"})


_CHILDREN = {}


def genre_children(gid):
    """楽天ブックスのジャンル木で gid の子ジャンル [(id, name)]。葉なら []。"""
    if gid not in _CHILDREN:
        d = _get("BooksGenre/Search/20121128", {"booksGenreId": gid}) or {}
        kids = []
        for c in d.get("children") or []:
            c = c.get("child", c)
            if c.get("booksGenreId"):
                kids.append((c["booksGenreId"], c.get("booksGenreName") or ""))
        _CHILDREN[gid] = kids
    return _CHILDREN[gid]


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


def walk(query, gname):
    """1クエリを発売日降順でたどり、当月以降の本を rows に足す。
    return (ended, pages, api_pages, count) / ended = past(過去日付まで到達) / end(結果の最後まで) / cap(上限で打ち切り)
      / error(API が3回失敗= 取り切れていない。★「結果の終わり」と区別する)
    count = そのクエリの総ヒット数(過去分も含む。子ジャンルで分けた時の取りこぼし検算に使う)"""
    ended, api_pages, pg, count = "cap", None, 0, 0
    for pg in range(1, MAX_PAGES + 1):
        d = books(query, pg)
        if d is None:
            ended = "error"
            break
        items = d.get("Items") or []
        if not items:
            ended = "end"
            break
        api_pages = d.get("pageCount") or api_pages
        count = int(d.get("count") or count)
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
            ended = "past"
            break
        if api_pages and pg >= int(api_pages):
            # 検索結果の最終頁まで読んだ。ただし API が100頁で頭打ちなら、その先(3,001件目〜)は届かない
            ended = "cap" if int(api_pages) >= API_MAX_PAGES else "end"
            break
    return ended, pg, api_pages, count


def describe(query):
    s = query["booksGenreId"]
    if "availability" in query:
        s += f"/{AVAILABILITY.get(query['availability'], query['availability'])}"
    if "size" in query:
        s += f"/{SIZES.get(query['size'], query['size'])}"
    return s


def splits(query):
    """上限にかかったクエリの分け方を、取りこぼしの無い順に返す [(名前, 分けたクエリ群)]。
    ① 子ジャンル ② 判型(判型の無い本が少し在る) ③ 在庫状況(★品切れの本は availability が空で、どの値でも引けない)"""
    out = []
    if "availability" not in query and "size" not in query:
        kids = genre_children(query["booksGenreId"])
        if kids:
            out.append(("子ジャンル", [{**query, "booksGenreId": k} for k, _ in kids]))
    if "size" not in query:
        out.append(("判型", [{**query, "size": s} for s in SIZES]))
    if "availability" not in query:
        out.append(("在庫状況", [{**query, "availability": a} for a in AVAILABILITY]))
    return out


_WALKED = {}  # 取得済みクエリ → 総ヒット数


def harvest(query, gname, depth, log, info=None):
    """walk して、上限で打ち切られたら splits() の順に分けて取り直す。
    分けた先の総ヒット数の合計が親に届けば(=分け方に漏れが無い)そこで終わり、届かなければ次の分け方でも取り直す
    (重複は seen で落ちる)。
    return (取り切れなかったクエリ[空なら完走], このクエリの総ヒット数, 漏れのある分け方で終えたクエリ)"""
    key = frozenset(query.items())
    if key in _WALKED:
        # 判型→在庫状況 と 在庫状況→判型 で同じ組み合わせに2回来る。本は取得済み・警告も1回目で記録済み
        return [], _WALKED[key], []
    ended, pages, api_pages, count = walk(query, gname)
    _WALKED[key] = count
    if info is not None:
        info.update(ended=ended, pages=pages, api_pages=api_pages, count=count)
    if ended == "error":
        return [describe(query) + f"(API失敗 p{pages})"], count, []
    if ended != "cap":
        return [], count, []
    if depth >= MAX_DEPTH:
        return [describe(query)], count, []
    left, lossy = [], []
    for how, subs in splits(query):
        log.append(f"{describe(query)} {pages}頁で上限 → {how}{len(subs)}に分けて取り直し")
        total = 0
        for sq in subs:
            l, c, ls = harvest(sq, gname, depth + 1, log)
            left += l
            lossy += ls
            total += c
        if total >= count:
            return left, count, lossy
        log.append(f"{describe(query)} {how}の合計{total} < 親{count}(分け方に漏れ)")
    if not splits(query):
        return [describe(query)], count, []
    # 全ての分け方を使っても合計が親に届かない = 在庫状況で引けない品切れ本が列の後ろ(当月の発売済み)に残りうる
    return left, count, lossy + [describe(query)]


status = {}
for gid, gname in SUBGENRES.items():
    n_before, calls_before = len(rows), N_CALLS
    log, info = [], {}
    # ★上限で打ち切られたら(= 列の後ろ=当月〜近い未来が落ちている)自動で分けて取り直す
    left, _, lossy = harvest({"booksGenreId": gid}, gname, 0, log, info)
    ended, pages, api_pages = info["ended"], info["pages"], info["api_pages"]
    limit = min(MAX_PAGES, API_MAX_PAGES)
    status[gname] = {"genre": gid, "pages": pages, "limit": limit, "api_pageCount": api_pages,
                     "kept": len(rows) - n_before, "calls": N_CALLS - calls_before, "ended": ended,
                     "auto_split": bool(log), "split_log": log, "unresolved": left, "lossy": lossy,
                     "truncated": bool(left), "near_limit": ended != "cap" and pages >= WARN_RATIO * limit}
    tag = "★取り切れず" if left else (ended if ended != "cap" else "自動細分で完走")
    print(f"  {gname}: 累計{len(rows)}件 (p{pages}まで・{tag})", flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
n_unknown = sum(1 for r in rows if r["unknown_date"])
from collections import Counter
dist = Counter(r["ym"] for r in rows if r["ym"])
print(f"完了: {len(rows)}件 (発売未定{n_unknown}) → {OUT}  / API呼び出し {N_CALLS}回")
print("月分布:", dict(sorted(dist.items())))

# ★取りこぼし検査(最後に出す=読み飛ばされないように)
json.dump({"at": datetime.datetime.now().isoformat(timespec="seconds"), "max_pages": MAX_PAGES, "genres": status},
          open(os.path.join(os.path.dirname(OUT) or ".", "harvest-status.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
split = [g for g, s in status.items() if s["auto_split"]]
trunc = [g for g, s in status.items() if s["truncated"]]
near = [g for g, s in status.items() if s["near_limit"]]
if split:
    print("\n自動細分: 上限にかかったジャンルを分けて取り直した")
    for g in split:
        for ln in status[g]["split_log"][:12]:
            print(f"   ・{g}: {ln}")
lossy = [g for g, s in status.items() if s["lossy"]]
if near:
    print("\n(情報)上限まで余裕が少ないジャンル: 今回は分けずに取り切れた・上限を超えたら自動細分が働く")
    for g in near:
        s = status[g]
        print(f"   ・{g}: {s['pages']}/{s['limit']}頁 = {s['pages'] * 100 // s['limit']}%")
if lossy:
    print("\n★ 取りこぼし注意: 分けても総数が親に届かないクエリがある = 品切れ(在庫状況が空)・判型の無い本はどの分け方でも引けない")
    for g in lossy:
        for q in status[g]["lossy"]:
            print(f"   ・{g}: {q}")
    print("   → 漏れうるのは列の後ろ=「当月に発売済みで品切れ」の本。発売前(予約受付中)の日次で取れていれば実害なし")
if trunc:
    print("\n★★ 取りこぼし警告: 取り切れないクエリがある(自動細分しても頁の上限にかかる / API失敗)= 当月〜近い未来の新刊が落ちている")
    for g in trunc:
        for q in status[g]["unresolved"]:
            print(f"   ★ {g}: {q}")
    print("   → API失敗なら時間を置いて再実行。上限なら分け方を足す(出版社別など)まで、このまま進めると取りこぼす")
elif not lossy:
    worst = max(status.items(), key=lambda kv: kv[1]["pages"] / kv[1]["limit"]) if status else None
    if worst:
        extra = "(自動細分あり)" if split else ""
        print(f"\n取りこぼし検査: OK 全ジャンル取り切れた{extra}(分けずに取った最大 {worst[0]} {worst[1]['pages']}/{worst[1]['limit']}頁)")
