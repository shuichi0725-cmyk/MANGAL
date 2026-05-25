"""(1) audit の scope 確認 = 種2 全件 vs 本番候補 subset。
(2) 「倉田百三」 の 種2 上 実態 = 何が 入っているか。
"""
import sqlite3
from pathlib import Path

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

print("=== audit scope 確認 ===")
print()
print("[全体件数]")
print(f"  series 総数 : {con.execute('SELECT COUNT(*) FROM series').fetchone()[0]:,}")
print(f"  editions    : {con.execute('SELECT COUNT(*) FROM editions').fetchone()[0]:,}")
print(f"  volumes 総数: {con.execute('SELECT COUNT(*) FROM volumes').fetchone()[0]:,}")
adult_count = con.execute(
    "SELECT COUNT(*) FROM series WHERE adult_score > 0"
).fetchone()[0]
print(f"  adult_score > 0 の series: {adult_count:,}")
excluded = con.execute(
    "SELECT COUNT(*) FROM series_excluded"
).fetchone()[0]
print(f"  series_excluded (= 既に排除済): {excluded:,}")

print()
print("[audit script 仕様]")
print("  → 種2 全 volumes/editions/series を SELECT、 filter は:")
print("    - is_extra=1 除外、 number 整数化可のみ、 max 3-300 のみ")
print("    - adult / 漫画以外 / series_excluded の フィルター = なし")
print("  → 結論: 本番 yml に入らない record も 含めて gap 検出している")

print()
print("=== 「倉田百三」 probe ===")
srows = con.execute(
    "SELECT id, qid, title, subtitle, year_started, year_ended, adult_score, genres "
    "FROM series WHERE title LIKE '%倉田百三%' ORDER BY id"
).fetchall()
for r in srows:
    print(f"  sid={r['id']}, qid={r['qid']!r}, title={r['title']!r}, "
          f"sub={r['subtitle']!r}, adult={r['adult_score']}, genres={r['genres']!r}")

if not srows:
    print("  (no series found)")
    raise SystemExit

ids = [r["id"] for r in srows]
ph = ",".join("?" * len(ids))

print()
print("[editions]")
erows = con.execute(
    f"SELECT id, series_id, type, label, imprint FROM editions WHERE series_id IN ({ph})",
    ids,
).fetchall()
for r in erows:
    print(f"  eid={r['id']}, sid={r['series_id']}, type={r['type']}, "
          f"label={r['label']!r}, imprint={r['imprint']!r}")

print()
print("[volumes]")
for e in erows:
    vols = con.execute(
        "SELECT number, volume_label, madb_book_id, isbn13, release_date "
        "FROM volumes WHERE edition_id=? ORDER BY id", (e["id"],),
    ).fetchall()
    print(f"  eid={e['id']} ({len(vols)} vol):")
    for v in vols:
        print(f"    number={v['number']!r:<6} label={v['volume_label']!r:<30} "
              f"madb={v['madb_book_id']!r:<10} isbn={v['isbn13']!r:<15} date={v['release_date']!r}")

print()
print("=== sources (= 種1 raw) 確認 ===")
for e in erows:
    vols = con.execute(
        "SELECT madb_book_id FROM volumes WHERE edition_id=?", (e["id"],),
    ).fetchall()
    for v in vols:
        if not v["madb_book_id"]:
            continue
        src = con.execute(
            "SELECT raw_json FROM sources WHERE ref_table='volumes' AND ref_id IN "
            "(SELECT id FROM volumes WHERE madb_book_id=? LIMIT 1) LIMIT 1",
            (v["madb_book_id"],),
        ).fetchone()
        if src:
            print(f"  madb={v['madb_book_id']}: raw 200 chars =")
            print(f"    {src['raw_json'][:500]!r}")
