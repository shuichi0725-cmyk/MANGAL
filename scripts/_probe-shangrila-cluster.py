"""新 norm 適用後の シャングリラフロンティア 関連 cluster を 確認。"""
import sqlite3
import sys
sys.path.insert(0, "scripts")
# importlib で audit script の norm_title を 再利用
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

rows = con.execute(
    "SELECT id, qid, title, subtitle FROM series "
    "WHERE title LIKE '%シャングリラ%フロンティア%' "
    "OR (title LIKE '%シャングリラ%' AND subtitle LIKE '%クソゲー%')"
).fetchall()

print("=== シャングリラフロンティア 関連 cluster ===")
print(f"{'sid':>6} {'qid':<12} cluster_key                                   title|sub")
print("-" * 130)
for r in rows:
    if r["qid"]:
        ckey = f"qid:{r['qid']}"
    else:
        norm = audit.norm_title(r["title"], r["subtitle"])
        ckey = f"title:{norm}"
    print(f"{r['id']:>6} {(r['qid'] or '-'):<12} {ckey:<45} {r['title']!r}|{r['subtitle']!r}")
