"""AKIRA型 edition分裂の調査(read-only)。

①promote の get_editions_with_volumes が AKIRA deluxe分裂を実際に統合するか検証
②全DB走査: 「同type・imprint違い」(=promoteが自動統合する型)の規模
③残る問題: 同一作品が「別type」に割れ巻番号が重複(=自動統合されない)ケースを炙り出し
"""
import sys, sqlite3, importlib.util
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path("C:/Users/shuic/code/mangal")
spec = importlib.util.spec_from_file_location("promote", ROOT / "scripts/_promote-bulk-v2.py")
pm = importlib.util.module_from_spec(spec); sys.argv = ["x"]; spec.loader.exec_module(pm)

con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")

# ① AKIRA 検証
print("=== ① AKIRA(qid:Q378710|name:AKIRA)を promote で実生成 ===")
sid = con.execute("SELECT id FROM series WHERE series_key=?", ("qid:Q378710|name:AKIRA",)).fetchone()
if sid:
    eds = pm.get_editions_with_volumes(con, [sid[0]])
    for ed in eds:
        nums = [v["number"] for v in ed["volumes"]]
        print(f"  最終edition: type={ed['type']} imprint={ed['imprint']} {len(nums)}巻 番号={nums}")
print("  → deluxe が[1-6]に統合されていれば分裂解決済")

# ② 全DB: 同type・複数imprint の規模(promoteが自動統合する型)
print("\n=== ② 同type・複数imprint(=promoteが自動統合)の規模 ===")
rows = con.execute("""SELECT series_id, type, imprint FROM editions""").fetchall()
by_st = defaultdict(set)
for s, t, imp in rows:
    by_st[(s, t)].add(imp or "")
multi_imprint = sum(1 for v in by_st.values() if len(v) >= 2)
print(f"  同(series,type)で imprint 2種以上: {multi_imprint:,} 群(=自動統合対象、 AKIRA deluxe型)")

# ③ 残る問題: 同series で「別type」が巻番号を重複保有(=同一版が別type誤分類の疑い)
print("\n=== ③ 残課題候補: 別typeが巻番号を重複(自動統合されない)===")
# series_id -> type -> set(numbers>0)
typ_nums = defaultdict(lambda: defaultdict(set))
for s, t, n in con.execute("""SELECT e.series_id, e.type, v.number
                              FROM editions e JOIN volumes v ON v.edition_id=e.id WHERE v.number>0"""):
    typ_nums[s][t].add(n)
suspects = []
for s, tmap in typ_nums.items():
    types = list(tmap.keys())
    if len(types) < 2: continue
    for i in range(len(types)):
        for j in range(i + 1, len(types)):
            a, b = tmap[types[i]], tmap[types[j]]
            if not a or not b: continue
            ov = len(a & b); mn = min(len(a), len(b))
            # 小さい方の70%以上が重複 = 同一版が別type誤分類の疑い
            if mn >= 2 and ov / mn >= 0.7:
                suspects.append((s, types[i], len(a), types[j], len(b), ov))
print(f"  別type巻番号70%+重複の series: {len(suspects):,}(=文庫/愛蔵の再編=正当・問題なし)")

# ④ 真の残課題: 別typeが「補完関係」(重複ゼロ+union連続)= 同一版の別type誤分類
print("\n=== ④ ★真の残課題: 別typeが補完関係(同一版がtype割れ)===")
comp = []
for s, tmap in typ_nums.items():
    types = list(tmap.keys())
    if len(types) < 2: continue
    for i in range(len(types)):
        for j in range(i + 1, len(types)):
            a, b = tmap[types[i]], tmap[types[j]]
            if len(a) < 2 or len(b) < 2: continue
            if a & b: continue  # 重複あり=別版なので除外
            u = a | b
            # union が 1..max 連続、 かつ 各々は単独で連続でない(=割れている)
            contiguous = (min(u) == 1 and max(u) == len(u))
            a_gap = (max(a) - min(a) + 1) != len(a)
            b_gap = (max(b) - min(b) + 1) != len(b)
            if contiguous and (a_gap or b_gap):
                comp.append((s, types[i], sorted(a), types[j], sorted(b)))
print(f"  補完関係(type割れ疑い)の series: {len(comp):,}")
for s, t1, na, t2, nb in comp[:20]:
    title = con.execute("SELECT title FROM series WHERE id=?", (s,)).fetchone()[0]
    print(f"    「{title[:22]}」 {t1}{na} + {t2}{nb}")
con.close()
