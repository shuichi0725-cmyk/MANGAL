"""C 案 = カラー override + 強 drop 例外 の dry-run sim。

logic:
- title prefix drop (= 既存 「英訳・」 等) → 無条件 drop
- title contains drop (= 既存「セレクション」「ガイドブック」等) hit + 強 drop hit → drop
- title contains drop hit + 強 drop なし + カラー override hit → keep
- title contains drop hit + 強 drop なし + カラー override なし → drop
- drop hit なし → keep

KEEP_OVERRIDE = ["フルカラー", "総カラー", "オールカラー", "カラー版", "カラーエディション"]
STRONG_DROP   = ["セレクション", "傑作選", "傑作集", "短編集", "特集号", "総集編", "ベストセレクション"]

副作用確認:
- 既存 drop されている sid のうち、 override で keep に翻る sid を 列挙
- ユーザ判断材料
"""
from __future__ import annotations
import sqlite3
import sys
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]; sys.argv = ["_", "--no-filter"]
spec.loader.exec_module(audit); sys.argv = saved

KEEP_OVERRIDE = ["フルカラー", "総カラー", "オールカラー", "カラー版", "カラーエディション"]
STRONG_DROP = ["セレクション", "傑作選", "傑作集", "短編集", "特集号", "総集編", "ベストセレクション"]


def title_passes_new(title):
    if not title: return True
    t = title.strip()
    for pat in audit.DROP_TITLE_PREFIX_PATTERNS:
        if t.startswith(pat):
            return False
    drop_hits = [p for p in audit.DROP_TITLE_CONTAINS_PATTERNS if p in t]
    if not drop_hits:
        return True
    # drop hit ある = 強 drop ある? 強 drop あれば override 無効
    if any(p in t for p in STRONG_DROP):
        return False
    # 強 drop なし + keep override hit ある → keep に翻す
    if any(p in t for p in KEEP_OVERRIDE):
        return True
    return False


con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row
rows = con.execute("SELECT id, title FROM series WHERE title IS NOT NULL").fetchall()

n_old_keep_new_drop = 0  # 旧 keep → 新 drop
n_old_drop_new_keep = 0  # 旧 drop → 新 keep (= override 効果)
saved_examples = []
removed_examples = []

for r in rows:
    t = r["title"]
    old_ok = audit.title_passes(t)
    new_ok = title_passes_new(t)
    if old_ok != new_ok:
        vc = con.execute("SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=?", (r["id"],)).fetchone()[0]
        if old_ok and not new_ok:
            n_old_keep_new_drop += 1
            if len(removed_examples) < 30:
                removed_examples.append((r["id"], t, vc))
        else:
            n_old_drop_new_keep += 1
            if len(saved_examples) < 30:
                saved_examples.append((r["id"], t, vc))

print(f"=== C 案 dry-run sim ===\n")
print(f"旧 drop → 新 keep (= override で救済): {n_old_drop_new_keep} sid")
print(f"旧 keep → 新 drop (= 副作用 / 引き締め): {n_old_keep_new_drop} sid")
print()
print(f"--- 救済される sid (= 新 keep) 例 ---")
for sid, t, vc in saved_examples:
    print(f"  sid={sid:>6} vc={vc:>3} '{t}'")
print()
if removed_examples:
    print(f"--- 新たに drop される sid 例 ---")
    for sid, t, vc in removed_examples:
        print(f"  sid={sid:>6} vc={vc:>3} '{t}'")
