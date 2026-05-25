"""うる星やつら 各 edition の 総ページ数 実測。

1. 種2 で うる星やつら sid 取得 + 各 edition の madb_book_id list
2. 種1 metadata101.json から 各 madb_id の schema:numberOfPages 取得
3. edition 別 集計
"""
import sqlite3
import re

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

# うる星やつら main sid=36054 の 全 edition + madb_id
rows = con.execute("""
    SELECT e.id AS eid, e.type, e.imprint, v.madb_book_id, v.number
    FROM editions e
    JOIN volumes v ON v.edition_id=e.id
    WHERE e.series_id=36054 AND v.is_extra=0 AND v.madb_book_id IS NOT NULL
    ORDER BY e.id, CAST(v.number AS INTEGER)
""").fetchall()

# madb_id を edition 別 grouping
by_edition = {}
all_madb_ids = set()
for r in rows:
    by_edition.setdefault((r["eid"], r["type"], r["imprint"]), []).append(r["madb_book_id"])
    all_madb_ids.add(r["madb_book_id"])

print(f"total madb_id: {len(all_madb_ids)}")
print(f"editions: {len(by_edition)}")

# 種1 から numberOfPages 取得
pages_by_madb = {}
NUM_RE = re.compile(r'(\d+)\s*p')
cur_id = None
cur_pages = None
target_set = all_madb_ids
with open(".cache/madb/metadata101.json", encoding="utf-8") as f:
    for line in f:
        m_id = re.search(r"/id/(M\d+)", line)
        if m_id:
            if cur_id in target_set and cur_pages:
                pages_by_madb[cur_id] = cur_pages
            cur_id = m_id.group(1)
            cur_pages = None
            continue
        m_p = re.search(r'"schema:numberOfPages":\s*"([^"]+)"', line)
        if m_p:
            v = m_p.group(1)
            mn = NUM_RE.search(v)
            if mn:
                cur_pages = int(mn.group(1))
    if cur_id in target_set and cur_pages:
        pages_by_madb[cur_id] = cur_pages

print(f"pages found for: {len(pages_by_madb)}/{len(all_madb_ids)} madb_ids")
print()

# edition 別 集計
print(f"=== うる星やつら 各 edition 総ページ数 ===")
print(f"{'eid':>6} {'type':<10} {'vols':>5} {'pages_found':>11} {'total_p':>8} {'avg_p':>6}  imprint")
results = []
for (eid, type_, imp), mids in by_edition.items():
    total_p = sum(pages_by_madb.get(m, 0) for m in mids)
    found = sum(1 for m in mids if m in pages_by_madb)
    avg = total_p // found if found else 0
    print(f"{eid:>6} {type_:<10} {len(mids):>5} {found:>11} {total_p:>8} {avg:>6}  {imp!r}")
    results.append((type_, imp, len(mids), found, total_p, avg))

# 主軸候補 (= 通常/ワイド/文庫) 比較
print()
print("=== 主軸候補 (= standard 主 + bunkobon + wideban) 比率 ===")
mains = [r for r in results if r[0] in ("standard", "bunkobon", "wideban") and r[4] > 0]
if mains:
    mx = max(r[4] for r in mains)
    for r in mains:
        ratio = r[4] / mx * 100
        print(f"  {r[0]:<10} {r[1]!r:<55} vols={r[2]:>3} total={r[4]:>6}p  比率={ratio:>5.1f}%")
