"""高橋留美子 (= qid=Q219948) 紐付き 全 sid を 列挙。

確認:
1. 全 sid + title 一覧
2. title 別 (= 作品単位) で edition_type ごとの max/present/gap
3. 現状 audit cluster (= qid 単独 統合) で 全部 union したらどうなるか
4. 「真の抜けマスク」 が 実在するか
"""
from __future__ import annotations
import sqlite3
import sys
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]
sys.argv = ["_probe", "--no-filter"]
spec.loader.exec_module(audit)
sys.argv = saved

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

# 高橋留美子 = Q219948
QID = "Q219948"

srows = con.execute(
    "SELECT id, title, subtitle FROM series WHERE qid=? ORDER BY title, id", (QID,)
).fetchall()
print(f"=== qid={QID} (高橋留美子) 紐付き = {len(srows)} sid ===\n")

# title 集約 = 同 title (norm) を 1 グループに
import unicodedata
def norm(s):
    if not s: return ""
    return "".join(c.lower() for c in s if unicodedata.category(c)[0] not in ("P", "Z") and c not in "ー―~〜")

groups = {}  # norm_title → list of sid
for r in srows:
    nt = norm(r["title"])
    groups.setdefault(nt, []).append(r)

print(f"unique title (norm 集約後): {len(groups)}\n")

# 各 title group ごとに edition_type 集計
results_per_title = []
for nt, rs in sorted(groups.items(), key=lambda x: -len(x[1])):
    sids = [r["id"] for r in rs]
    ph = ",".join("?" * len(sids))
    vrows = con.execute(f"""
        SELECT v.number, v.is_extra, e.type, e.imprint, s.title
        FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id
        WHERE e.series_id IN ({ph})
    """, sids).fetchall()
    nums_by_type = {}
    for v in vrows:
        if v["is_extra"]: continue
        if not audit.edition_passes(v["type"], v["imprint"]): continue
        if not audit.title_passes(v["title"]): continue
        try:
            n = int(v["number"])
            if n > 0: nums_by_type.setdefault(v["type"], set()).add(n)
        except (ValueError, TypeError): pass
    representative = rs[0]["title"]
    results_per_title.append((representative, sids, nums_by_type))

for title, sids, nums_by_type in results_per_title:
    sids_str = ",".join(str(s) for s in sids[:5]) + ("..." if len(sids) > 5 else "")
    print(f"  '{title}' ({len(sids)} sid: {sids_str})")
    if not nums_by_type:
        print(f"    (no valid numbers)")
    for edt, nums in sorted(nums_by_type.items()):
        mx = max(nums)
        missing = sorted(set(range(1, mx+1)) - nums)
        miss = ",".join(str(x) for x in missing[:15])
        if len(missing) > 15: miss += f"... ({len(missing)} total)"
        gap_mark = "" if not missing else f"  gap=[{miss}]"
        print(f"    {edt:<10}: max={mx:>3}, pres={len(nums):>3}, gap={len(missing):>3}{gap_mark}")
    print()

# 現状 audit (= qid 統合) シミュレーション
print("=" * 60)
print("=== 現状 audit cluster (= qid:Q219948 統合 union) ===")
print("=" * 60)
all_sids = [r["id"] for r in srows]
ph = ",".join("?" * len(all_sids))
vrows = con.execute(f"""
    SELECT v.number, v.is_extra, e.type, e.imprint, s.title
    FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id
    WHERE e.series_id IN ({ph})
""", all_sids).fetchall()
union_by_type = {}
for v in vrows:
    if v["is_extra"]: continue
    if not audit.edition_passes(v["type"], v["imprint"]): continue
    if not audit.title_passes(v["title"]): continue
    try:
        n = int(v["number"])
        if n > 0: union_by_type.setdefault(v["type"], set()).add(n)
    except (ValueError, TypeError): pass
print()
for edt, nums in sorted(union_by_type.items()):
    mx = max(nums)
    missing = sorted(set(range(1, mx+1)) - nums)
    print(f"  {edt:<10}: max={mx}, pres={len(nums)}, gap={len(missing)}  missing={missing[:20]}")
