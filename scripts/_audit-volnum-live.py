#!/usr/bin/env python3
"""
巻番号サニティ(本番manga.v2直読み, READ-ONLY): page×edition 単位で
 ①GAP    = 番号に抜け (= [1,3,4] で 2 欠け)
 ②OFFSET = 番号が1始まりでない (= 全5巻なのに 4,5,6,7,8 型)
 ③DUP    = 同番号が複数巻
を検出。多版は版ごとに判定。単巻(<2)は対象外。
出力: data/seeds/volnum-gap.tsv / volnum-offset.tsv / volnum-dup.tsv
"""
import sys, glob, time, os
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L

src = sys.argv[1] if len(sys.argv) > 1 else "data/manga.v2"
t0 = time.time()
gaps, offsets, dups = [], [], []
n = 0
for f in glob.glob(os.path.join(src, "*.yml")):
    try: d = yaml.load(open(f, encoding="utf-8"), Loader=L)
    except: continue
    if not isinstance(d, dict): continue
    n += 1
    slug = d.get("slug"); title = d.get("title")
    for e in (d.get("editions") or []):
        label = e.get("label") or e.get("type") or "?"
        vols = e.get("volumes") or []
        nums = [v.get("number") for v in vols if isinstance(v.get("number"), int)]
        if len(nums) < 2: continue
        cnt = len(nums)
        uniq = sorted(set(nums))
        # ③DUP = 重複番号
        if len(uniq) < cnt:
            from collections import Counter
            dd = [k for k, c in Counter(nums).items() if c > 1]
            dups.append((slug, title, label, cnt, sorted(dd)))
            continue
        lo, hi = uniq[0], uniq[-1]
        span = hi - lo + 1
        # ①GAP = 範囲内に抜け
        if span > len(uniq):
            missing = [x for x in range(lo, hi + 1) if x not in set(uniq)]
            gaps.append((slug, title, label, uniq, missing))
        # ②OFFSET = 抜け無いが1始まりでない (= 4,5,6,7,8 型)。 0始まり(vol0)は除外。
        elif lo > 1:
            offsets.append((slug, title, label, uniq))

def write(path, rows, header):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + "\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")

gaps.sort(key=lambda r: -len(r[4]))
offsets.sort(key=lambda r: r[3][0] if r[3] else 0, reverse=True)
write("data/seeds/volnum-gap.tsv", [(s, t, l, ",".join(map(str, u)), ",".join(map(str, m))) for s, t, l, u, m in gaps],
      "slug\ttitle\tedition\tnumbers\tmissing")
write("data/seeds/volnum-offset.tsv", [(s, t, l, ",".join(map(str, u))) for s, t, l, u in offsets],
      "slug\ttitle\tedition\tnumbers")
write("data/seeds/volnum-dup.tsv", [(s, t, l, c, ",".join(map(str, dd))) for s, t, l, c, dd in dups],
      "slug\ttitle\tedition\tcount\tdup_numbers")

print(f"走査 {n}ページ / {time.time()-t0:.0f}秒")
print(f"①GAP(抜け 例1,3,4): {len(gaps)}")
print(f"②OFFSET(1始まりでない 例4-8): {len(offsets)}")
print(f"③DUP(同番号重複): {len(dups)}")
print("--- GAP上位10 ---")
for s, t, l, u, m in gaps[:10]:
    print(f"  {s} [{l}] {u} 欠け{m}  ({t})")
print("--- OFFSET上位10 ---")
for s, t, l, u in offsets[:10]:
    print(f"  {s} [{l}] {u}  ({t})")
