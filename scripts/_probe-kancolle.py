"""艦隊これくしょん-艦これ-コミックアラカルト の 実態確認。

仮説: 「舞鶴鎮守府編19」 のような 複合表記 を 種2 build が
number="19" として 格納 → audit が「1-18 抜け」 と 誤判定。

確認:
- 関連 series row 全部 (= 各鎮守府編 が 別 series か?)
- volumes の number + volume_label 構造
- subtitle 構造
"""
import sqlite3

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

print("=== series (= title に 「コミックアラカルト」 含む) ===")
srows = con.execute(
    "SELECT id, qid, title, subtitle, year_started, year_ended "
    "FROM series WHERE title LIKE '%コミックアラカルト%' "
    "ORDER BY id"
).fetchall()
for r in srows:
    print(f"  id={r['id']:>6}, qid={r['qid']!r:<12}, title={r['title']!r}, sub={r['subtitle']!r}")

ids = [r["id"] for r in srows]
if not ids:
    raise SystemExit("(none)")
ph = ",".join("?" * len(ids))

print()
print("=== editions ===")
erows = con.execute(
    f"SELECT id, series_id, type, imprint FROM editions WHERE series_id IN ({ph}) ORDER BY series_id, id",
    ids,
).fetchall()
for r in erows:
    print(f"  edition.id={r['id']:>6} series_id={r['series_id']:>6} imprint={r['imprint']!r}")

print()
print("=== volumes per edition (= number / volume_label / madb_book_id) ===")
for e in erows:
    vols = con.execute(
        "SELECT number, volume_label, madb_book_id, isbn13, release_date "
        "FROM volumes WHERE edition_id=? ORDER BY CAST(number AS INTEGER), id",
        (e["id"],),
    ).fetchall()
    if not vols:
        continue
    print(f"  edition.id={e['id']} ({len(vols)} volumes):")
    for v in vols[:30]:
        print(f"    number={v['number']!r:<6} label={v['volume_label']!r:<30} "
              f"madb={v['madb_book_id']!r:<10} isbn={v['isbn13']!r:<15} date={v['release_date']!r}")
    if len(vols) > 30:
        print(f"    ... ({len(vols) - 30} more)")
