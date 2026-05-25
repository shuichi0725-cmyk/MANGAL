"""こち亀 全 sid に 既存 filter を 適用 sim。

確認:
1. title filter (= DROP_TITLE_PREFIX_PATTERNS + DROP_TITLE_CONTAINS_PATTERNS)
2. edition filter (= KEEP_EDITION_TYPES + DROP_IMPRINT_PATTERNS)
3. 種3 紐付き
4. ユーザ採用 (= 1-201 + 文庫 26 巻) vs 現状 filter の 過不足
"""
from __future__ import annotations
import sqlite3
import sys
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]
sys.argv = ["_", "--no-filter"]
spec.loader.exec_module(audit)
sys.argv = saved

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row
seed3_keys, seed3_qids = audit.load_seed3_keys()

srows = con.execute(
    "SELECT id, qid, series_key, title, subtitle FROM series "
    "WHERE title LIKE '%こちら葛飾区亀有%' OR title LIKE '%こちら亀有%' "
    "ORDER BY id"
).fetchall()
print(f"=== こち亀 関連 {len(srows)} sid に filter 適用 sim ===\n")

n_keep = 0
n_drop = 0
for s in srows:
    by_key = s["series_key"] in seed3_keys
    by_qid = s["qid"] and s["qid"] in seed3_qids
    seed3_ok = by_key or by_qid
    title_ok = audit.title_passes(s["title"])

    erows = con.execute(
        "SELECT id, type, imprint FROM editions WHERE series_id=?", (s["id"],)
    ).fetchall()
    keep_ed = []
    drop_ed = []
    for e in erows:
        vc = con.execute("SELECT COUNT(*) FROM volumes WHERE edition_id=?", (e["id"],)).fetchone()[0]
        if audit.edition_passes(e["type"], e["imprint"]):
            keep_ed.append((e, vc))
        else:
            drop_ed.append((e, vc))

    final_keep = seed3_ok and title_ok and keep_ed
    mark = "✓KEEP" if final_keep else "✗DROP"
    reasons = []
    if not seed3_ok: reasons.append("seed3=NG")
    if not title_ok: reasons.append("title-drop")
    if not keep_ed: reasons.append("all-editions-drop")

    print(f"  [{mark}] sid={s['id']:>6} title={s['title']!r} sub={s['subtitle']!r}")
    if reasons:
        print(f"          reasons: {','.join(reasons)}")
    for e, vc in keep_ed:
        print(f"          KEEP eid={e['id']} type={e['type']} imp={e['imprint']!r} vols={vc}")
    for e, vc in drop_ed:
        print(f"          DROP eid={e['id']} type={e['type']} imp={e['imprint']!r} vols={vc}")
    if final_keep: n_keep += 1
    else: n_drop += 1
    print()

print(f"=== summary: keep={n_keep} sid, drop={n_drop} sid ===")
