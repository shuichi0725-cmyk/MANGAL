"""フリガナ補完Step2: 残ページ(MADB未カバー)のkanaを NDL by-ISBN で取得。
入力: .cache/kana-residual.tsv (series_key, isbn, title)
出力: .cache/kana-ndl.json {series_key: kana_segmented}  ※resumable
NDL dc:title の dcndl:transcription(本題ヨミ、 空白区切り)を採用。副題 " : " 以降は除外。
"""
import sys, os, json, re, html, time
import urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = ROOT + "/.cache/kana-residual.tsv"
OUT = ROOT + "/.cache/kana-ndl.json"

rows = []
for line in open(RES, encoding="utf-8"):
    p = line.rstrip("\n").split("\t")
    if len(p) >= 2:
        rows.append((p[0], p[1]))  # (series_key, isbn)

cache = {}
done_isbn = set()
if os.path.exists(OUT):
    cache = json.load(open(OUT, encoding="utf-8"))

def fetch(isbn):
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl"
           "&maximumRecords=2&query=" + urllib.parse.quote('isbn="%s"' % isbn))
    x = html.unescape(urllib.request.urlopen(url, timeout=30).read().decode("utf-8"))
    m = re.search(r"<dc:title>.*?<dcndl:transcription>(.*?)</dcndl:transcription>", x, re.S)
    if not m:
        return ""
    yomi = m.group(1).strip()
    return yomi.split(" : ")[0].strip()  # 本題のみ

todo = [(sk, i) for sk, i in rows if sk not in cache]
print("全%d / 既取得%d / 今回%d" % (len(rows), len(cache), len(todo)))
ok = miss = err = 0
for n, (sk, isbn) in enumerate(todo, 1):
    try:
        k = fetch(isbn)
        if k:
            cache[sk] = k; ok += 1
        else:
            cache[sk] = ""; miss += 1
    except Exception:
        cache[sk] = ""; err += 1
    if n % 50 == 0:
        json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d (ok=%d miss=%d err=%d)" % (n, len(todo), ok, miss, err))
    time.sleep(0.25)
json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("完了: ok=%d miss=%d err=%d → %s" % (ok, miss, err, OUT))
