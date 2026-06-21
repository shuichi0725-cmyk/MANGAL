#!/usr/bin/env python3
"""
巻番号と冊数の不整合を検出(READ-ONLY): 版の volume番号集合が 1..N でない物。
A: 単巻なのに番号≥2 (= 一冊しかないのに二巻、画面の型)。
B: 複数巻だが 1始まりでない (offset残)。
C: 複数巻で内部欠け (gap残)。
出力 data/seeds/volnum-mismatch.tsv。
"""
import sys, glob, os, json
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L

cats = {"A_single_ge2": [], "B_offset": [], "C_gap": []}
n = 0
for fp in glob.glob("data/manga.v2/*.yml"):
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: continue
    if not isinstance(d, dict): continue
    n += 1
    slug = d.get("slug"); title = str(d.get("title") or "")
    for e in (d.get("editions") or []):
        nums = sorted(v.get("number") for v in (e.get("volumes") or []) if isinstance(v.get("number"), int))
        if not nums: continue
        cnt = len(nums); mn = nums[0]; mx = nums[-1]
        expect = list(range(1, cnt + 1))
        if nums == expect: continue   # 正常 1..N
        lab = e.get("label") or e.get("type")
        rec = (slug, title[:30], lab, cnt, f"{nums[:8]}")
        if cnt == 1 and mn >= 2:
            cats["A_single_ge2"].append(rec)
        elif mn > 1:
            cats["B_offset"].append(rec)
        else:
            cats["C_gap"].append(rec)
        break  # 代表版1つで十分

print(f"走査 {n}作")
for k, rows in cats.items():
    print(f"  {k}: {len(rows)}")
    with open(f"data/seeds/volnum-mismatch-{k}.tsv", "w", encoding="utf-8") as f:
        f.write("slug\ttitle\tedition\tcnt\tnums\n")
        for r in rows: f.write("\t".join(str(x) for x in r) + "\n")
print("\n=== A(単巻なのに番号≥2) サンプル ===")
for r in cats["A_single_ge2"][:12]: print("  ", r[0], "|", r[1], "| 第%s巻のみ" % r[4].strip("[]"))
print("=== B(offset残) サンプル ===")
for r in cats["B_offset"][:6]: print("  ", r[0], "|", r[1], "|", r[4])
print("=== C(gap残) サンプル ===")
for r in cats["C_gap"][:6]: print("  ", r[0], "|", r[1], "|", r[4])
