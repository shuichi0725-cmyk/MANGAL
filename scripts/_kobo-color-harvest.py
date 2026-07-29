#!/usr/bin/env python3
"""電子カラー版柱①: 楽天Koboから「カラー版」全冊をharvestする。

- 対象: title=カラー版(部分一致=フルカラー版/完全カラー版も内包) × koboGenreId=101904(コミック)
- ★page上限100×hits30=3,000/クエリ < 総数3,779 → sort=+releaseDate と -releaseDate の
  2パスunion(itemNumberでdedup)で全量回収(NDL年代スライスと同じ発想の軽量版)。
- レート: 1.3秒/req厳守・429/エラーは backoff。
- 出力: .cache/kobo-color-raw.jsonl(1行1冊)。再実行=全上書き(5分で引き直せる)。

使い方: python scripts/_kobo-color-harvest.py
"""
import sys, io, json, time, urllib.request, urllib.parse
from urllib.parse import urlparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "kobo-color-raw.jsonl"
GENRE = "101904"  # コミック(ラノベ/実用のカラー版ノイズを入口で遮断)
KEEP = ("title", "subTitle", "seriesName", "author", "authorKana", "titleKana",
        "publisherName", "itemNumber", "itemUrl", "affiliateUrl", "largeImageUrl",
        "itemPrice", "salesDate", "koboGenreId", "salesType")

env = {}
for ln in open(ROOT / ".env.local", encoding="utf-8"):
    if "=" in ln:
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
RREF = env.get("RAKUTEN_REFERER", "https://github.com/")
_o = urlparse(RREF)
RORG = f"{_o.scheme}://{_o.netloc}"


def kobo(params, retries=4):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env.get("RAKUTEN_ACCESS_KEY", ""),
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "format": "json",
         "formatVersion": "2", "hits": 30}
    p.update(params)
    u = "https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "Mozilla/5.0"})
    for at in range(retries):
        try:
            time.sleep(1.3)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if at == retries - 1:
                raise
            wait = (2, 10, 45)[min(at, 2)]
            print(f"  retry({e.__class__.__name__}) {wait}s...", flush=True)
            time.sleep(wait)


def sweep(sort, seen, rows):
    page = 1
    total = None
    while page <= 100:
        r = kobo({"title": "カラー版", "koboGenreId": GENRE, "sort": sort, "page": page})
        if total is None:
            total = r.get("count")
            print(f"sort={sort}: count={total}", flush=True)
        items = r.get("Items") or []
        if not items:
            break
        for it in items:
            key = it.get("itemNumber") or it.get("itemUrl")
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({k: it.get(k) for k in KEEP})
        if page % 20 == 0:
            print(f"  page {page} 累計{len(rows)}", flush=True)
        if page * 30 >= (total or 0):
            break
        page += 1


def main():
    seen: set = set()
    rows: list = []
    sweep("+releaseDate", seen, rows)
    sweep("-releaseDate", seen, rows)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"完了: {len(rows)}冊 → {OUT}")


if __name__ == "__main__":
    main()
