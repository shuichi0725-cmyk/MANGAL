"""フリガナ補完Step2: MADB未カバーの残ページを特定し、NDL照会用の代表ISBNを出す。
残 = data/manga ソース(=ページ)の series_key が:
  - db series.title_kana 空 かつ
  - title-kana-fill.yml(MADB回収)に未存在
出力: .cache/kana-residual.tsv  (series_key, isbn, title)  ※NDL by-ISBN照会の入力
"""
import sqlite3, sys, os, glob, yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = ROOT + "/.cache/db-v2.sqlite"

# MADB fill 済 series_key
filldoc = yaml.safe_load(open(ROOT + "/data/seeds/title-kana-fill.yml", encoding="utf-8")) or {}
fillkeys = {e["key"] for e in (filldoc.get("fills") or [])}
print("MADB fill 済:", len(fillkeys))

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
# series_key -> (id, title_kana, title)
skey2 = {}
for r in con.execute("SELECT id, series_key, title_kana, title FROM series"):
    skey2[r["series_key"]] = (r["id"], r["title_kana"], r["title"])
# id -> 代表ISBN(最小)
id2isbn = {}
for r in con.execute("SELECT e.series_id AS sid, v.isbn13 AS isbn FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL ORDER BY v.isbn13"):
    id2isbn.setdefault(r["sid"], r["isbn"])

residual = {}
n_src = 0
for f in glob.glob(ROOT + "/data/manga/*.yml"):
    n_src += 1
    try:
        d = yaml.safe_load(open(f, encoding="utf-8"))
    except Exception:
        continue
    sk = d.get("_skey")
    if not sk or sk in fillkeys or sk not in skey2:
        continue
    sid, tk, title = skey2[sk]
    if tk:  # db に kana 有り = 対象外
        continue
    isbn = id2isbn.get(sid)
    if isbn:
        residual[sk] = (isbn, title)

with open(ROOT + "/.cache/kana-residual.tsv", "w", encoding="utf-8") as out:
    for sk, (isbn, title) in sorted(residual.items()):
        out.write("%s\t%s\t%s\n" % (sk, isbn, title))
print("ソース %d / 残ページ(NDL要) %d → .cache/kana-residual.tsv" % (n_src, len(residual)))
