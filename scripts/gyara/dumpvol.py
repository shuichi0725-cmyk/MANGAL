# -*- coding: utf-8 -*-
# 種2クラスタの巻明細dump (ギャラ型是正用)
import sqlite3, sys

db = sqlite3.connect(".cache/db-v2.sqlite")
db.row_factory = sqlite3.Row
cur = db.cursor()
ecols = [r[1] for r in cur.execute("PRAGMA table_info(editions)")]

for sid in sys.argv[1:]:
    s = cur.execute("SELECT * FROM series WHERE id=?", (sid,)).fetchone()
    print("=" * 78)
    print("sid", sid, "|", s["title"] if s else "?", "| key", s["series_key"] if s else "")
    for e in cur.execute("SELECT * FROM editions WHERE series_id=?", (sid,)).fetchall():
        lab = " ".join(str(e[c]) for c in ("edition_type", "imprint", "publisher_key", "label")
                       if c in ecols and e[c])
        print(" [ed%s] %s" % (e["id"], lab))
        for r in cur.execute(
                "SELECT number, isbn13, release_date, volume_label FROM volumes "
                "WHERE edition_id=? ORDER BY number, release_date", (e["id"],)):
            print("    v%-5s %-14s %-12s %s" % (
                r["number"], r["isbn13"] or "-", r["release_date"] or "-", r["volume_label"] or ""))
