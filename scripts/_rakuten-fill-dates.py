"""楽天ブックスAPIで月精度ISBNの「日」をバックフィルする収穫機。 ★純粋追加・再開可能。

  - 対象 = data/manga.v2 の release_date が YYYY-MM(日欠落)の ISBN
  - 1 req/秒(QPS規約)。 レスポンス全体を .cache/rakuten-isbn.jsonl に追記キャッシュ
    (= salesDate の他、 書影URL/価格も将来用に保存。 キャッシュ済みISBNはAPIを叩かない)
  - 採用条件: 楽天 salesDate の年月 == 既存の年月 の時のみ「日」を採用(別版/誤ヒット防止)。
    年月不一致は review 行き。 「頃」付きは day_approx として採用(表示で「頃」は出さない)
  - 出力 seed: data/seeds/release-date-fill.json {isbn13: 'YYYY-MM-DD'}(追記マージ)
    promote 反映は別途(volume release_date が月精度の時のみ seed で補完)

usage: python _rakuten-fill-dates.py [--limit N] [--newest-first]
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "rakuten-isbn.jsonl"
SEED = ROOT / "data" / "seeds" / "release-date-fill.json"
REVIEW = ROOT / ".cache" / "rakuten-date-review.tsv"

env = dict(
    l.strip().split("=", 1)
    for l in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines()
    if "=" in l
)
ORIGIN = "https://mangal.shuichi0725.workers.dev"


def call_api(isbn):
    qs = urllib.parse.urlencode({
        "applicationId": env["RAKUTEN_APP_ID"],
        "accessKey": env["RAKUTEN_ACCESS_KEY"],
        "isbn": isbn,
        "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""),
        "outOfStockFlag": "1",   # ★在庫切れも返す(旧作の発売日・書影が取れる。ユーザ指摘 2026-06-12)
        "format": "json",
    })
    req = urllib.request.Request(
        "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + qs
    )
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0 MANGAL")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def parse_sales_date(s):
    """'1991年02月08日' / '2016年06月03日頃' / '1996年02月' → (YYYY-MM, DD or None, approx)"""
    if not s:
        return None, None, False
    approx = "頃" in s
    m = re.search(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", s)
    if not m:
        return None, None, approx
    ym = f"{m.group(1)}-{int(m.group(2)):02d}"
    day = int(m.group(3)) if m.group(3) else None
    return ym, day, approx


def month_only_isbns():
    out = []
    pat = re.compile(r"isbn13:\s*'?(\d{13})'?\n(?:\s+cover_url:.*\n)?\s+release_date:\s*'?(\d{4}-\d{2})'?\s*\n")
    for f in (ROOT / "data" / "manga.v2").glob("*.yml"):
        txt = f.read_text(encoding="utf-8")
        for m in pat.finditer(txt):
            out.append((m.group(1), m.group(2)))
    return out


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    targets = month_only_isbns()
    if "--newest-first" in sys.argv:
        targets.sort(key=lambda x: x[1], reverse=True)
    print(f"月精度ISBN: {len(targets):,} 件")

    done = set()
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["isbn"])
            except Exception:
                pass
    print(f"キャッシュ済: {len(done):,} 件(スキップ)")

    seed = json.loads(SEED.read_text(encoding="utf-8")) if SEED.exists() else {}
    stats = {"filled": 0, "no_hit": 0, "ym_mismatch": 0, "no_day": 0, "err": 0, "cached_skip": 0}
    review_rows = []
    n_called = 0

    cf = CACHE.open("a", encoding="utf-8")
    try:
        for isbn, ym in targets:
            if limit is not None and n_called >= limit:
                break
            if isbn in done or isbn in seed:
                stats["cached_skip"] += 1
                continue
            try:
                d = call_api(isbn)
            except Exception as e:
                stats["err"] += 1
                print(f"  ERR {isbn}: {str(e)[:60]}")
                time.sleep(3)
                continue
            n_called += 1
            items = d.get("Items", [])
            it = items[0]["Item"] if items else {}
            cf.write(json.dumps({"isbn": isbn, "item": it}, ensure_ascii=False) + "\n")
            cf.flush()
            r_ym, day, approx = parse_sales_date(it.get("salesDate"))
            if not it:
                stats["no_hit"] += 1
            elif r_ym != ym:
                stats["ym_mismatch"] += 1
                review_rows.append((isbn, ym, it.get("salesDate", ""), it.get("title", "")[:30]))
            elif day is None:
                stats["no_day"] += 1
            else:
                seed[isbn] = f"{ym}-{day:02d}"
                stats["filled"] += 1
            if n_called % 100 == 0:
                SEED.write_text(json.dumps(seed, ensure_ascii=False, indent=0), encoding="utf-8")
                print(f"  …{n_called:,}件処理 {stats}")
            time.sleep(1.05)
    finally:
        cf.close()
        SEED.parent.mkdir(parents=True, exist_ok=True)
        SEED.write_text(json.dumps(seed, ensure_ascii=False, indent=0), encoding="utf-8")
        with REVIEW.open("a", encoding="utf-8") as f:
            for r in review_rows:
                f.write("\t".join(str(x) for x in r) + "\n")

    print(f"\n=== 結果(API {n_called:,}回) ===")
    print(stats)
    print(f"seed累計: {len(seed):,} 件 → {SEED}")


if __name__ == "__main__":
    main()
