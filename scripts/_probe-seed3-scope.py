"""種3 (= series-supplement-v2.yml) と 種2 sqlite の 紐付け状況確認。

確認:
  1. 種3 entry 数
  2. 種3 key と 種2 series.series_key の マッチ数
  3. 種3 紐付き series が 持つ volume 数
  4. これが audit の正しい scope か 判定
"""
import sqlite3
from pathlib import Path
import yaml

SEED3 = Path("data/seeds/series-supplement-v2.yml")
DB = Path(".cache/db-v2.sqlite")

print(f"=== 種3 = {SEED3} ===")
with SEED3.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)
seed3_entries = data.get("series", [])
print(f"  entries: {len(seed3_entries):,}")

# key 例 sample
print(f"  key 例 (= 先頭 5 件):")
for e in seed3_entries[:5]:
    print(f"    {e['key'][:120]}")

seed3_keys = {e["key"] for e in seed3_entries}

print()
print(f"=== 種2 sqlite = {DB} ===")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
total_series = con.execute("SELECT COUNT(*) FROM series").fetchone()[0]
print(f"  series 総数: {total_series:,}")

# series_key で マッチ件数
matched = 0
matched_sids = []
chunk = 500
key_list = list(seed3_keys)
for i in range(0, len(key_list), chunk):
    batch = key_list[i:i+chunk]
    ph = ",".join("?" * len(batch))
    rows = con.execute(
        f"SELECT id FROM series WHERE series_key IN ({ph})", batch
    ).fetchall()
    matched += len(rows)
    matched_sids.extend(r["id"] for r in rows)

print(f"  種3 key で 種2 series.series_key マッチ: {matched:,} 件")
print(f"  紐付き比率: {matched / total_series * 100:.1f}% (= 種2 全体 {total_series:,} のうち)")
print(f"  種3 側 マッチ率: {matched / len(seed3_keys) * 100:.1f}% (= 種3 {len(seed3_keys):,} のうち)")

if matched_sids:
    ph = ",".join("?" * min(len(matched_sids), 1000))
    # 全 sid で 集計したいので 全部 chunk
    total_eds = 0
    total_vols = 0
    for i in range(0, len(matched_sids), chunk):
        batch = matched_sids[i:i+chunk]
        ph = ",".join("?" * len(batch))
        total_eds += con.execute(
            f"SELECT COUNT(*) FROM editions WHERE series_id IN ({ph})", batch
        ).fetchone()[0]
        total_vols += con.execute(
            f"SELECT COUNT(*) FROM volumes v "
            f"JOIN editions e ON e.id=v.edition_id "
            f"WHERE e.series_id IN ({ph})", batch
        ).fetchone()[0]
    print()
    print(f"  種3 紐付き series が 持つ:")
    print(f"    editions: {total_eds:,}")
    print(f"    volumes : {total_vols:,}")

# qid join も試す (= 種3 key の qid 部分 と 種2 series.qid)
qid_keys = set()
for e in seed3_entries:
    k = e["key"]
    if k.startswith("qid:"):
        # 'qid:Q12345|...'
        qid = k.split("|", 1)[0][4:]
        qid_keys.add(qid)
print()
print(f"=== qid 経由 join (= 種3 key の qid: 部分 で 種2 series.qid マッチ) ===")
print(f"  種3 中 qid 持ち: {len(qid_keys):,}")
matched_qid = 0
matched_qid_sids = set()
for i in range(0, len(qid_keys), chunk):
    batch = list(qid_keys)[i:i+chunk]
    ph = ",".join("?" * len(batch))
    rows = con.execute(
        f"SELECT id, qid FROM series WHERE qid IN ({ph})", batch
    ).fetchall()
    matched_qid += len(rows)
    matched_qid_sids.update(r["id"] for r in rows)
print(f"  qid マッチ series 数: {matched_qid:,} (= series 単位)")
print(f"  qid マッチ 種2 sid 数: {len(matched_qid_sids):,}")

print()
print("=== union (= series_key OR qid マッチ) ===")
combined = set(matched_sids) | matched_qid_sids
print(f"  combined 種2 sid: {len(combined):,}")
print(f"  種2 全 {total_series:,} のうち {len(combined) / total_series * 100:.1f}%")
