"""はじめの一歩 (= MADB ID C288046) の 種2 上の 実態 を 確認。

仮説: 同一シリーズが series_id 跨いで 複数登録されている → edition 集計だけでは
gap が 過大に出る。 series_key / qid / series.id 各 dimension で 何件あるか 確認。
"""
import sqlite3

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

print("=== series ===")
rows = con.execute(
    "SELECT id, series_key, qid, title, subtitle, year_started, year_ended "
    "FROM series WHERE title LIKE '%はじめの一歩%' ORDER BY id"
).fetchall()
for r in rows:
    print(f"  series.id={r['id']}, key={r['series_key']!r}, qid={r['qid']!r}, "
          f"title={r['title']!r}, sub={r['subtitle']!r}, {r['year_started']}〜{r['year_ended']}")

ids = [r["id"] for r in rows]
if not ids:
    print("(no series)")
    raise SystemExit

placeholder = ",".join("?" * len(ids))
print()
print("=== editions per series_id ===")
erows = con.execute(
    f"SELECT id, series_id, type, label, imprint, year_started, year_ended "
    f"FROM editions WHERE series_id IN ({placeholder}) ORDER BY series_id, id",
    ids,
).fetchall()
for r in erows:
    print(f"  edition.id={r['id']}, series_id={r['series_id']}, type={r['type']}, "
          f"label={r['label']!r}, imprint={r['imprint']!r}")

print()
print("=== volume count per edition ===")
for e in erows:
    cnt = con.execute("SELECT COUNT(*) FROM volumes WHERE edition_id=?", (e["id"],)).fetchone()[0]
    nums = con.execute(
        "SELECT number FROM volumes WHERE edition_id=? ORDER BY CAST(number AS INTEGER)",
        (e["id"],),
    ).fetchall()
    num_list = [r["number"] for r in nums]
    print(f"  edition.id={e['id']} ({e['type']} [{e['label']}]): {cnt} volumes")
    if cnt <= 50:
        print(f"    numbers: {num_list}")
    else:
        print(f"    first 10: {num_list[:10]}, last 10: {num_list[-10:]}")

print()
print("=== series_key 系 全件 (= MADB ID 確認) ===")
keyrows = con.execute(
    "SELECT id, series_key, qid, title FROM series "
    "WHERE series_key LIKE '%C288046%' OR series_key LIKE '%ippo%' OR series_key LIKE '%ipppo%' OR title LIKE '%はじめの一歩%'"
).fetchall()
for r in keyrows:
    print(f"  id={r['id']}, key={r['series_key']!r}, qid={r['qid']!r}, title={r['title']!r}")
