"""楽天BooksBook APIで「まだ取得していない巻ISBN」を ISBN直引きで追加収穫する。
★前回の発売日収穫(_rakuten-fill-dates.py)は"日が欠けた巻"だけが対象だったため、
  最初から日付が揃っていた巻は一度も問い合わせておらず書影が無い。その不足分を埋める。

- 対象 = data/manga.v2 の全巻ISBN(ユニーク) − .cache/rakuten-isbn.jsonl 既収集
- ★プレビュー(.preview-data)該当ISBNを先頭に並べ、テスト環境の欠けを優先回収
- 1 req/秒(QPS規約)。応答全体(書影URL/価格/発売日/アフィリURL)を jsonl に追記
- 通信エラーは最大3回リトライ。失敗ISBNは未キャッシュのまま=次回再実行で再試行(再開可能)
- ★純粋追加: 既存キャッシュ行は不変。データ・seedは触らない(本番反映は別途 promote/cover-fill)

usage: python _rakuten-fill-covers.py [--limit N]
"""
import json, sys, time, glob, re
import urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "rakuten-isbn.jsonl"
PROD = ROOT / "data" / "manga.v2"
PREVIEW = ROOT / ".preview-data" / "manga"

env = dict(
    l.strip().split("=", 1)
    for l in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines()
    if "=" in l and not l.strip().startswith("#")
)
ORIGIN = "https://mangal.shuichi0725.workers.dev"
ISBN_RE = re.compile(r"isbn13:\s*'?(\d{13})'?")


def call_api(isbn):
    qs = urllib.parse.urlencode({
        "applicationId": env["RAKUTEN_APP_ID"],
        "accessKey": env["RAKUTEN_ACCESS_KEY"],
        "isbn": isbn,
        "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""),
        "outOfStockFlag": "1",
        "format": "json",
    })
    req = urllib.request.Request(
        "https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + qs)
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0 MANGAL")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def isbns_in(folder):
    s = set()
    for f in glob.glob(str(folder / "*.yml")):
        try:
            for m in ISBN_RE.findall(open(f, encoding="utf-8").read()):
                s.add(m)
        except Exception:
            pass
    return s


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    print("本番ISBN収集中…")
    prod = isbns_in(PROD)
    preview = isbns_in(PREVIEW) if PREVIEW.exists() else set()
    print(f"本番ユニーク巻ISBN: {len(prod):,} / プレビュー該当: {len(preview):,}")

    done = set()
    if CACHE.exists():
        with CACHE.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["isbn"])
                except Exception:
                    pass
    print(f"既収集(スキップ): {len(done):,}")

    todo = [i for i in prod if i not in done]
    # プレビュー該当を先頭へ(テスト環境の欠けを早く回収)
    todo.sort(key=lambda i: (i not in preview, i))
    print(f"追加収穫対象: {len(todo):,}(うちプレビュー {sum(1 for i in todo if i in preview):,} を先行)")

    stats = {"img": 0, "noimg": 0, "zero": 0, "err": 0}
    n = 0
    cf = CACHE.open("a", encoding="utf-8")
    try:
        for isbn in todo:
            if limit is not None and n >= limit:
                break
            d = None
            for attempt in range(3):
                try:
                    d = call_api(isbn)
                    break
                except Exception as e:
                    if attempt == 2:
                        stats["err"] += 1
                        print(f"  ERR {isbn}: {str(e)[:60]}")
                    else:
                        time.sleep(2 + attempt * 3)
            if d is None:
                time.sleep(1.05)
                continue
            n += 1
            items = d.get("Items", [])
            it = items[0]["Item"] if items else {}
            cf.write(json.dumps({"isbn": isbn, "item": it}, ensure_ascii=False) + "\n")
            cf.flush()
            if not it:
                stats["zero"] += 1
            else:
                img = it.get("largeImageUrl") or ""
                stats["img" if (img and "noimage" not in img) else "noimg"] += 1
            if n % 200 == 0:
                pct = n * 100 // max(1, min(len(todo), limit or len(todo)))
                print(f"  …{n:,}/{len(todo):,} ({pct}%) {stats}")
            time.sleep(1.05)
    finally:
        cf.close()

    print(f"\n=== 結果(API {n:,}回)===")
    print(stats)
    print(f"キャッシュ → {CACHE}")


if __name__ == "__main__":
    main()
