"""ジョジョの奇妙な冒険 全シリーズ 探索。
- title に「ジョジョ」 含む 全 series
- 第1〜9部 / 文庫 / 関連書 / アニメ版 / 海外版 等 全部 抽出
- 各 sid: 種3 紐付き / filter 通過 / volumes 数
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

# 「ジョジョ」 を 含む 全 series
srows = con.execute(
    "SELECT id, qid, series_key, title, subtitle FROM series "
    "WHERE title LIKE '%ジョジョ%' OR title LIKE '%JoJo%' OR title LIKE '%Jojo%' "
    "ORDER BY id"
).fetchall()
print(f"=== ジョジョ 関連 series 全件 = {len(srows)} sid ===\n")

# 各 sid: edition 状況 + 種3 紐付き + filter 判定
for s in srows:
    by_key = s["series_key"] in seed3_keys
    by_qid = s["qid"] and s["qid"] in seed3_qids
    seed3 = "[OK]" if (by_key or by_qid) else "[NG]"
    title_ok = audit.title_passes(s["title"])
    title_drop = " [TITLE-DROP]" if not title_ok else ""
    print(f"  sid={s['id']:>6} qid={s['qid']!r:<14} {seed3}{title_drop}")
    print(f"          title={s['title']!r}, sub={s['subtitle']!r}")
    erows = con.execute(
        "SELECT id, type, imprint FROM editions WHERE series_id=? ORDER BY id", (s["id"],)
    ).fetchall()
    for e in erows:
        ed_ok = audit.edition_passes(e["type"], e["imprint"])
        ed_mark = "KEEP" if ed_ok else "DROP"
        vcount = con.execute("SELECT COUNT(*) FROM volumes WHERE edition_id=?", (e["id"],)).fetchone()[0]
        # number 範囲
        nums = con.execute(
            "SELECT number FROM volumes WHERE edition_id=? AND is_extra=0",
            (e["id"],),
        ).fetchall()
        valid_nums = set()
        for n in nums:
            try:
                v = int(n["number"])
                if v > 0:
                    valid_nums.add(v)
            except (ValueError, TypeError):
                pass
        if valid_nums:
            min_n, max_n = min(valid_nums), max(valid_nums)
            nrange = f"min={min_n} max={max_n} present={len(valid_nums)}"
        else:
            nrange = "no valid numbers"
        print(f"    eid={e['id']:>6} type={e['type']:<10} imp={e['imprint']!r:<55} vols={vcount} → {ed_mark} ({nrange})")
    print()
