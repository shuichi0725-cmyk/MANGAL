"""シャングリラフロンティア 関連 series の 実態確認。

ユーザ指摘: 「シリーズ DB に 5 冊しかなく タイトル表記に揺れがある」。
audit v2 で max=25 / max=26 で gap=20/24 と検出されたが 過剰判定の可能性。
"""
import sqlite3

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

print("=== series (= title に 「シャングリラ」「フロンティア」 含む) ===")
rows = con.execute(
    "SELECT id, series_key, qid, title, subtitle, year_started, year_ended "
    "FROM series WHERE title LIKE '%シャングリラ%' OR title LIKE '%フロンティア%' "
    "ORDER BY id"
).fetchall()
for r in rows:
    print(f"  id={r['id']:>6}, qid={r['qid']!r:<12}, title={r['title']!r}, sub={r['subtitle']!r}")

ids = [r["id"] for r in rows]
if not ids:
    raise SystemExit("(no series)")
placeholder = ",".join("?" * len(ids))

print()
print("=== editions ===")
erows = con.execute(
    f"SELECT id, series_id, type, label, imprint FROM editions "
    f"WHERE series_id IN ({placeholder}) ORDER BY series_id, id",
    ids,
).fetchall()
for r in erows:
    print(f"  edition.id={r['id']:>6}, series_id={r['series_id']:>6}, type={r['type']:<10}, "
          f"imprint={r['imprint']!r}")

print()
print("=== volumes per edition (= number と isbn) ===")
for e in erows:
    vols = con.execute(
        "SELECT number, isbn13, release_date, volume_label "
        "FROM volumes WHERE edition_id=? ORDER BY CAST(number AS INTEGER), id",
        (e["id"],),
    ).fetchall()
    if not vols:
        continue
    print(f"  edition.id={e['id']} ({e['type']} [{e['imprint']}]): {len(vols)} volumes")
    for v in vols:
        print(f"    number={v['number']!r:<8} isbn={v['isbn13']!r:<16} "
              f"label={v['volume_label']!r:<10} date={v['release_date']!r}")
