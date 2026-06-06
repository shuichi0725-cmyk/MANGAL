"""title_kana 欠落 series を MADB(madb-isbn-kana.tsv)の巻ISBN読みから補完する fill seed を生成。
出力: data/seeds/title-kana-fill.yml  {fills: [{key, kana_segmented}]}
- kana は空白区切りのまま保持(空白除去=表示用 title_kana / 空白保持=slug生成用 segmented)。
- 副題(" : " 以降)は除外し本題のみ。 series の巻で最頻の読みを採用。
- db-v2 series.title_kana が空 の series のみ対象(純粋な補完)。種2/種3は不変。
"""
import sqlite3, sys, re
from collections import Counter, defaultdict
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
DB = ROOT + "/.cache/db-v2.sqlite"
MADB = ROOT + "/.cache/madb-isbn-kana.tsv"
OUT = ROOT + "/data/seeds/title-kana-fill.yml"

# ISBN -> kana(空白区切り)
isbn2kana = {}
with open(MADB, encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) >= 3 and p[2].strip():
            isbn2kana[p[0].strip()] = p[2].strip()
print("madb-isbn-kana:", len(isbn2kana))

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# 空 title_kana の series の id/series_key
empties = con.execute(
    "SELECT id, series_key FROM series WHERE title_kana IS NULL OR title_kana=''"
).fetchall()
print("空kana series:", len(empties))

# series_id -> [isbn]
sid2isbn = defaultdict(list)
for r in con.execute(
    "SELECT e.series_id AS sid, v.isbn13 AS isbn FROM volumes v JOIN editions e ON e.id=v.edition_id "
    "WHERE v.isbn13 IS NOT NULL"
):
    sid2isbn[r["sid"]].append(r["isbn"])

def main_kana(spaced):
    # 副題 " : " 以降を除外
    return spaced.split(" : ")[0].strip()

fills = []
hit = 0
for r in empties:
    sid, skey = r["id"], r["series_key"]
    kanas = []
    for isbn in sid2isbn.get(sid, []):
        k = isbn2kana.get(str(isbn))
        if k:
            kanas.append(main_kana(k))
    if not kanas:
        continue
    best = Counter(kanas).most_common(1)[0][0]
    if best:
        fills.append({"key": skey, "kana_segmented": best})
        hit += 1

fills.sort(key=lambda x: x["key"])
with open(OUT, "w", encoding="utf-8") as f:
    f.write("# title_kana 欠落 series を MADB巻ISBN読みから補完(scripts/_gen-kana-fill.py)。\n")
    f.write("# kana_segmented=空白区切り(表示は空白除去/slug生成は空白保持)。promoteが corr の次に読む。\n")
    yaml.safe_dump({"fills": fills}, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
print("fill生成:", hit, "件 →", OUT)
