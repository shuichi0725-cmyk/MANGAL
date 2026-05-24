"""ranma の db-v2 series_key と seed3 key 一致確認。"""
import sqlite3
from pathlib import Path

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row
rows = con.execute("SELECT id, title, subtitle, qid, series_key FROM series WHERE title LIKE '%らんま1/2%'").fetchall()
for r in rows:
    print(f"  id={r['id']}, title={r['title']!r}, sub={r['subtitle']!r}, qid={r['qid']}, key={r['series_key']!r}")
