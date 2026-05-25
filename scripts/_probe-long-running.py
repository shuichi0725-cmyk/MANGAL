"""長期連載 作品 (= 鬼平 / ゴルゴ / こち亀) の 取込状況 一括 probe。
- title に 該当ワード含む 全 series
- qid 紐付き / seed3 紐付き / edition + volume 状況
- 各部別 取込状況 一覧
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
seed3_keys, seed3_qids = audit.load_seed3_keys()

TARGETS = [
    ("鬼平犯科帳", ["%鬼平犯科帳%"]),
    ("ゴルゴ13", ["%ゴルゴ13%", "%ゴルゴ１３%"]),
    ("こち亀", ["%こちら葛飾区亀有%", "%こちら亀有%"]),
]

for name, patterns in TARGETS:
    print(f"\n{'='*60}")
    print(f"=== {name} ===")
    print(f"{'='*60}")
    where = " OR ".join("title LIKE ?" for _ in patterns)
    srows = con.execute(
        f"SELECT id, qid, title, subtitle FROM series WHERE {where} ORDER BY id",
        patterns,
    ).fetchall()
    print(f"  hit: {len(srows)} sid\n")

    # qid 別 集計
    qids = {}
    for r in srows:
        qids.setdefault(r["qid"] or "(none)", []).append(r["id"])

    for qid, sids in qids.items():
        ph = ",".join("?" * len(sids))
        # 各 edition_type ごとに number 集計
        rows = con.execute(f"""
            SELECT v.number, v.is_extra, e.type, e.imprint, s.title, s.id AS sid
            FROM volumes v
            JOIN editions e ON e.id=v.edition_id
            JOIN series s ON s.id=e.series_id
            WHERE e.series_id IN ({ph})
        """, sids).fetchall()
        nums_by_type = {}
        for r in rows:
            if r["is_extra"]:
                continue
            if not audit.edition_passes(r["type"], r["imprint"]):
                continue
            if not audit.title_passes(r["title"]):
                continue
            try:
                n = int(r["number"])
                if n > 0:
                    nums_by_type.setdefault(r["type"], set()).add(n)
            except (ValueError, TypeError):
                pass
        print(f"  --- qid={qid} ({len(sids)} sid: {sids[:8]}{'...' if len(sids)>8 else ''}) ---")
        for edt, nums in nums_by_type.items():
            mx = max(nums)
            missing = sorted(set(range(1, mx + 1)) - nums)
            miss_str = ",".join(str(x) for x in missing[:20])
            if len(missing) > 20:
                miss_str += f"... ({len(missing)} total)"
            print(f"    {edt:<10}: max={mx:>3}, present={len(nums):>3}, gap={len(missing):>3}  missing=[{miss_str}]")
        if not nums_by_type:
            print(f"    (no valid filter-passed numbers)")

    # title 別 一覧 (= subtitle 違いとか 表示)
    print(f"\n  --- title 別 list ---")
    title_set = {}
    for r in srows:
        key = (r["title"], r["subtitle"])
        title_set.setdefault(key, []).append(r["id"])
    for (t, sub), sids in sorted(title_set.items(), key=lambda x: (x[0][0] or "", x[0][1] or "")):
        sub_str = f" / sub='{sub}'" if sub else ""
        print(f"    [{','.join(str(s) for s in sids[:8])}{'...' if len(sids)>8 else ''}] {t!r}{sub_str}")
