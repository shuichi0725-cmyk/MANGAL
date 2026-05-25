"""「カラー」 keep override の 副作用 sim。

確認:
1. title or imprint に 「カラー」 word 含む series 全件 列挙
2. 各 sid を 3 分類:
   A. 「派生 + カラー」 = keep override 効果あり (= パーフェクトカラー型)
   B. 「主軸 (= 巻数最多) が カラー含む」 = カラー版が メイン (= 例: カラー専用作品)
   C. 「カラー含む 別 cluster (= 同 qid 内 主軸別)」 = 別作品で カラー word

軸:
- title 「カラー」「フルカラー」「総カラー」「オールカラー」「カラー版」 含む
- imprint も 別途 集計
"""
from __future__ import annotations
import re
import sqlite3
import sys
from collections import defaultdict
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]; sys.argv = ["_", "--no-filter"]
spec.loader.exec_module(audit); sys.argv = saved

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

COLOR_PATTERNS = ["フルカラー", "総カラー", "オールカラー", "カラー版", "カラーエディション", "カラー"]

# 全 series で title に カラー word 含む
print("=== title に カラー word 含む series 全件 ===\n")
rows = con.execute(
    "SELECT id, qid, title, subtitle FROM series WHERE title LIKE '%カラー%' ORDER BY qid, title"
).fetchall()
print(f"total: {len(rows)}\n")

# qid 別 集計 = 「派生か 主軸か」
by_qid = defaultdict(list)
for r in rows:
    by_qid[r["qid"] or "(none)"].append(r)

# 各 sid で 巻数取得
def vol_count(sid):
    return con.execute("SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=?", (sid,)).fetchone()[0]

# 同 qid 内 主軸 (= 巻数最多) との 比較
n_derivative = 0  # 派生 (= 巻数 < 主軸)
n_main = 0        # 主軸自体 が カラー
n_only = 0        # qid 内 1 sid のみ
n_no_qid = 0

derivative_examples = []
main_examples = []
only_examples = []
no_qid_examples = []

for qid, sids in by_qid.items():
    if qid == "(none)":
        for s in sids:
            n_no_qid += 1
            vc = vol_count(s["id"])
            if len(no_qid_examples) < 10:
                no_qid_examples.append((s["title"], vc))
        continue
    # 同 qid 全 sid (= カラー含まないも 含めて)
    all_sids = con.execute("SELECT id, title FROM series WHERE qid=?", (qid,)).fetchall()
    sid_to_vc = {s["id"]: vol_count(s["id"]) for s in all_sids}
    max_vc = max(sid_to_vc.values()) if sid_to_vc else 0
    main_sid = max(sid_to_vc, key=sid_to_vc.get) if sid_to_vc else None
    if len(all_sids) == 1:
        for s in sids:
            n_only += 1
            if len(only_examples) < 10:
                only_examples.append((qid, s["title"], sid_to_vc.get(s["id"], 0)))
        continue
    for s in sids:
        sid_vc = sid_to_vc.get(s["id"], 0)
        if s["id"] == main_sid:
            n_main += 1
            if len(main_examples) < 10:
                main_examples.append((qid, s["title"], sid_vc, max_vc))
        else:
            n_derivative += 1
            if len(derivative_examples) < 15:
                main_title = next((a["title"] for a in all_sids if a["id"] == main_sid), "?")
                derivative_examples.append((qid, s["title"], sid_vc, main_title, max_vc))

print(f"=== 分類結果 ===")
print(f"A. 派生 + カラー (= keep override 効果対象) : {n_derivative} sid")
print(f"B. 主軸自体が カラー (= カラー専用作品)      : {n_main} sid")
print(f"C. 同 qid 1 sid のみ                       : {n_only} sid")
print(f"D. qid なし                                : {n_no_qid} sid")
print()

print("--- A. 派生 + カラー (= override で keep される) ---")
for qid, t, vc, mt, mvc in derivative_examples:
    print(f"  qid={qid} sid_vc={vc} '{t}' (main_vc={mvc} '{mt}')")
print()
print("--- B. 主軸自体が カラー (= カラー専用作品 = 既に keep されている) ---")
for qid, t, vc, mvc in main_examples:
    print(f"  qid={qid} vc={vc}/{mvc} '{t}'")
print()
print("--- D. qid なし (= override でも影響なし、 通常 audit logic) ---")
for t, vc in no_qid_examples:
    print(f"  vc={vc} '{t}'")
