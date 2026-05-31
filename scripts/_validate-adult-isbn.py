"""adult FP候補(24件)を ISBN で楽天/Google Books に問い合わせて成人判定を裏取り。

入力: .cache/adult-fp24-isbn.tsv (series_key, title, author_ratio, isbns)
権威ソース(本単位ISBN):
  - 楽天ブックス BooksBook API   (env: RAKUTEN_APP_ID [+ RAKUTEN_ACCESS_KEY])
  - Google Books API             (env: GOOGLE_BOOKS_API_KEY 推奨、 無いと429)
判定:
  - 楽天: booksGenreId に成年コミック系 / adultFlag
  - Google: volumeInfo.maturityRating == MATURE
  → どちらも非adult = FP確定(全年齢) / どちらか adult = 維持

出力: .cache/adult-fp24-verdict.tsv。 ※調査のみ、 adult_score不変。
"""
import os, sys, csv, json, time, urllib.request, urllib.parse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(".cache/adult-fp24-isbn.tsv")
RAKUTEN_APP = os.environ.get("RAKUTEN_APP_ID")
GBOOKS_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")
UA = {"User-Agent": "MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)"}
# 楽天 BooksBook の成人系 genreId prefix(成年コミック等)。 実データで要確認。
RAKUTEN_ADULT_GENRE = ("001017002",)  # コミック>成年 想定、 走行時に実値で補正


def _get(url, retry=4):
    for i in range(retry):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (i + 1)); continue
            return {"_err": e.code}
        except Exception as e:
            time.sleep(3); continue
    return {"_err": "retry_exhausted"}


def rakuten(isbn):
    if not RAKUTEN_APP:
        return None
    u = ("https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404?"
         + urllib.parse.urlencode({"applicationId": RAKUTEN_APP, "isbn": isbn, "format": "json"}))
    d = _get(u)
    items = d.get("Items") or []
    if not items:
        return ("notfound", "")
    it = items[0].get("Item", {})
    gid = str(it.get("booksGenreId", ""))
    adult = any(gid.startswith(p) for p in RAKUTEN_ADULT_GENRE) or "成年" in str(it.get("title", ""))
    return ("ADULT" if adult else "allages", gid)


def gbooks(isbn):
    base = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    if GBOOKS_KEY:
        base += f"&key={GBOOKS_KEY}"
    d = _get(base)
    if d.get("_err"):
        return (f"err:{d['_err']}", "")
    items = d.get("items") or []
    if not items:
        return ("notfound", "")
    vi = items[0].get("volumeInfo", {})
    mr = vi.get("maturityRating", "")
    return ("ADULT" if mr == "MATURE" else "allages", mr)


def main():
    if not RAKUTEN_APP:
        print("（注）RAKUTEN_APP_ID 未設定 → 楽天はスキップ。 https://webservice.rakuten.co.jp/ で無料発行。")
    if not GBOOKS_KEY:
        print("（注）GOOGLE_BOOKS_API_KEY 未設定 → 無認証で試行(429 になりやすい)。 GCPで無料発行推奨。")
    rows = list(csv.DictReader(SRC.open(encoding="utf-8"), delimiter="\t"))
    out = []
    for r in rows:
        isbns = [x for x in (r["isbns"] or "").split(",") if x][:2]
        rk = gb = "noisbn"
        for isbn in isbns:
            if RAKUTEN_APP:
                v = rakuten(isbn); rk = v[0] if v else rk; time.sleep(0.4)
            if GBOOKS_KEY or True:
                v = gbooks(isbn); gb = v[0]; time.sleep(0.4)
            if rk == "ADULT" or gb == "ADULT":
                break
        verdict = "維持(adult)" if (rk == "ADULT" or gb == "ADULT") else (
            "FP確定(全年齢)" if (rk in ("allages", "notfound", "noisbn") and gb in ("allages", "notfound")) else "不明")
        out.append((r["title"], rk, gb, verdict))
        print(f"  {r['title'][:26]:<26} 楽天={rk:<10} google={gb:<10} → {verdict}")
    with open(".cache/adult-fp24-verdict.tsv", "w", encoding="utf-8") as f:
        f.write("title\trakuten\tgoogle\tverdict\n")
        for t, rk, gb, v in out:
            f.write(f"{t}\t{rk}\t{gb}\t{v}\n")
    nfp = sum(1 for _, _, _, v in out if v.startswith("FP"))
    print(f"\nFP確定(全年齢): {nfp} / {len(out)}  → これらを override に追加候補")
    print("wrote .cache/adult-fp24-verdict.tsv")


if __name__ == "__main__":
    main()
