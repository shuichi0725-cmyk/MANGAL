import sqlite3
from pathlib import Path
con = sqlite3.connect('.cache/db-v2.sqlite')
con.row_factory = sqlite3.Row
out = Path('.cache/jyu-check.txt')
lines = []
lines.append('=== Q11328345 柔侠伝 系 entry ===')
for r in con.execute("SELECT id, series_key, title, title_kana FROM series WHERE qid='Q11328345' AND title LIKE '%伝%'").fetchall():
    lines.append(f'  id={r["id"]}')
    lines.append(f'    title    ={r["title"]!r}')
    lines.append(f'    title_cp ={[hex(ord(c)) for c in r["title"]]}')
    lines.append(f'    title_kana    ={r["title_kana"]!r}')
    if r["title_kana"]:
        lines.append(f'    title_kana_cp ={[hex(ord(c)) for c in r["title_kana"]]}')
    lines.append('')
out.write_text('\n'.join(lines), encoding='utf-8')
print(f'wrote {out}')
