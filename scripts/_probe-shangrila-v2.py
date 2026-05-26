"""シャングリラフロンティア の 完全 probe (= 種3 + filter + audit 視点)。

確認:
  1. 関連 series 全 sid + 種3 紐付き
  2. 各 edition の filter 通過/弾く 判定
  3. cluster 統合状況 (= 統合後 何 vol が gap 算出 対象)
  4. 真の 抜け巻
"""
from __future__ import annotations
import sqlite3
import sys
sys.path.insert(0, "scripts")
import yaml

# audit script の filter logic を 流用
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
# ただし audit.main() を実行しないよう sys.argv を 退避
saved_argv = sys.argv[:]
sys.argv = ["_probe", "--no-filter"]  # filter load 時の判定を avoid (= module load 不要)
# モジュール load (filter constants/functions だけ取る)
spec.loader.exec_module(audit)
sys.argv = saved_argv

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

# 種3 紐付き
seed3_keys, seed3_qids = audit.load_seed3_keys()

print("=== シャングリラフロンティア 関連 series ===")
srows = con.execute(
    "SELECT id, qid, series_key, title, subtitle FROM series "
    "WHERE title LIKE '%シャングリラ%フロンティア%' OR title LIKE '%シャングリラ・フロンティア%' "
    "ORDER BY id"
).fetchall()
for r in srows:
    by_key = r["series_key"] in seed3_keys
    by_qid = r["qid"] and r["qid"] in seed3_qids
    seed3_mark = "[OK]" if (by_key or by_qid) else "[NG]"
    print(f"  sid={r['id']:>6}, qid={r['qid']!r}, title={r['title']!r}, sub={r['subtitle']!r}  seed3={seed3_mark}")

ids = [r["id"] for r in srows]
ph = ",".join("?" * len(ids))

print()
print("=== editions per series + filter 判定 ===")
erows = con.execute(
    f"SELECT e.id, e.series_id, e.type, e.imprint, s.title "
    f"FROM editions e JOIN series s ON s.id=e.series_id "
    f"WHERE e.series_id IN ({ph}) ORDER BY e.series_id, e.id",
    ids,
).fetchall()

for e in erows:
    ed_ok = audit.edition_passes(e["type"], e["imprint"])
    title_ok = audit.title_passes(e["title"])
    vcount = con.execute("SELECT COUNT(*) FROM volumes WHERE edition_id=?", (e["id"],)).fetchone()[0]
    final = "KEEP" if (ed_ok and title_ok) else "DROP"
    why = []
    if not ed_ok: why.append("edition")
    if not title_ok: why.append("title")
    print(f"  sid={e['series_id']:>6} eid={e['id']:>6} type={e['type']:<10} imp={e['imprint']!r}")
    print(f"      vols={vcount}, filter={final} {('('+','.join(why)+')' if why else '')}")
    if final == "KEEP":
        # 巻番号を 表示
        vols = con.execute(
            "SELECT number, volume_label, isbn13 FROM volumes WHERE edition_id=? "
            "ORDER BY CAST(number AS INTEGER), id", (e["id"],)
        ).fetchall()
        nums = [v["number"] for v in vols]
        print(f"      numbers={nums}")

print()
print("=== audit cluster_key 計算 ===")
# audit と 同 logic
import unicodedata, re
import importlib
# alias_to_main
alias_to_main = {}
with open("data/seeds/series-merge.yml", encoding="utf-8") as f:
    for entry in (yaml.safe_load(f) or []):
        for a in entry.get("aliases", []) or []:
            alias_to_main[a] = entry["main"]

# 全 series scan for title_to_qid + main_to_qid
all_series = con.execute("SELECT id, qid, title, subtitle FROM series").fetchall()
title_to_qid = {}
main_to_qid = {}
for r in all_series:
    if r["qid"]:
        t = alias_to_main.get(r["title"], r["title"])
        title_to_qid.setdefault(audit.norm_title(t, r["subtitle"]), r["qid"])
    if r["qid"] and r["title"] in alias_to_main:
        main_to_qid.setdefault(alias_to_main[r["title"]], r["qid"])

cluster_map = {}
for r in srows:
    eff = alias_to_main.get(r["title"], r["title"])
    if r["qid"]:
        ck = f"qid:{r['qid']}"
    elif eff in main_to_qid:
        ck = f"qid:{main_to_qid[eff]}"
    else:
        norm = audit.norm_title(eff, r["subtitle"])
        if norm in title_to_qid:
            ck = f"qid:{title_to_qid[norm]}"
        else:
            ck = f"title:{norm}"
    cluster_map.setdefault(ck, []).append(r["id"])

for ck, sids in cluster_map.items():
    print(f"  cluster_key={ck}")
    print(f"    sids={sids}")

print()
print("=== 統合後 集計 (= 各 cluster_key の standard edition 集計) ===")
for ck, sids in cluster_map.items():
    ph2 = ",".join("?" * len(sids))
    # standard かつ filter 通過の volumes
    vrows = con.execute(
        f"""
        SELECT v.number, v.is_extra, e.type, e.imprint, s.title
        FROM volumes v
        JOIN editions e ON e.id=v.edition_id
        JOIN series s ON s.id=e.series_id
        WHERE e.series_id IN ({ph2})
        """, sids,
    ).fetchall()
    nums = set()
    for v in vrows:
        if v["is_extra"]:
            continue
        if not audit.edition_passes(v["type"], v["imprint"]):
            continue
        if not audit.title_passes(v["title"]):
            continue
        try:
            n = int(v["number"])
            if n > 0:
                nums.add(n)
        except (ValueError, TypeError):
            pass
    if nums:
        mx = max(nums)
        missing = sorted(set(range(1, mx + 1)) - nums)
        print(f"  cluster={ck}")
        print(f"    nums={sorted(nums)}")
        print(f"    max={mx}, present={len(nums)}, missing={missing}")
