# -*- coding: utf-8 -*-
"""Wikipedia発売日 掃引 STEP1 = 候補記事の raw wikitext を取得する。

入力: .cache/jawiki-title-hits.json  (= scripts/_wiki-date-candidates.py が作る
      [stem, 本番title, 巻数, jawiki記事名] の配列)
出力: .cache/wiki-sweep/<safe-key>.txt   (1記事1ファイル。既存はskip=中断再開可)

礼儀: 1.1s/req・UA明示。11,268件で約3.4時間。
usage: python scripts/_wiki-date-fetch.py [--limit N]
"""
import argparse, io, json, os, re, sys, time
import urllib.request, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, ".cache", "jawiki-title-hits.json")
OUT = os.path.join(ROOT, ".cache", "wiki-sweep")
REUSE = os.path.join(ROOT, ".cache", "wiki-sample")   # 見積り時に取った分を使い回す
UA = {"User-Agent": "MANGAL-bot/1.0 (manga database; contact: github.com/mediaarts-db)"}


def key(name):
    return re.sub(r"[^0-9A-Za-z぀-ヿ一-鿿]", "_", name)[:80]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rows = json.load(io.open(CAND, encoding="utf-8"))
    # 記事名でユニーク化(同じ記事に複数頁がぶら下がることがある)
    names = []
    seen = set()
    for stem, ti, n, wname in rows:
        if wname not in seen:
            seen.add(wname)
            names.append(wname)
    print("候補記事(ユニーク):", len(names), flush=True)

    got = skipped = reused = failed = 0
    t0 = time.time()
    for i, name in enumerate(names, 1):
        if a.limit and got >= a.limit:
            break
        fp = os.path.join(OUT, key(name) + ".txt")
        if os.path.exists(fp):
            skipped += 1
            continue
        rp = os.path.join(REUSE, key(name) + ".txt")
        if os.path.exists(rp):
            io.open(fp, "w", encoding="utf-8").write(
                io.open(rp, encoding="utf-8", errors="replace").read())
            reused += 1
            continue
        url = ("https://ja.wikipedia.org/w/index.php?action=raw&title="
               + urllib.parse.quote(name))
        try:
            body = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30
            ).read().decode("utf-8", "replace")
        except Exception as e:
            body = "__MISSING__ %s" % e
            failed += 1
        io.open(fp, "w", encoding="utf-8").write(body)
        got += 1
        time.sleep(1.1)
        if got % 200 == 0:
            el = time.time() - t0
            rate = got / el if el else 0
            left = (len(names) - i) / rate / 3600 if rate else 0
            print("  %d/%d 取得 (再利用%d skip%d 失敗%d) 残り約%.1fh"
                  % (i, len(names), reused, skipped, failed, left), flush=True)
    print("DONE 取得%d 再利用%d skip%d 失敗%d / %.1f分"
          % (got, reused, skipped, failed, (time.time() - t0) / 60), flush=True)


main()
