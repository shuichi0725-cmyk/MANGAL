"""recent-ongoing-volumes.jsonl を集計して TSV に落とす(read-only)。"""
import csv
import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in (ROOT / ".cache" / "recent-ongoing-volumes.jsonl").open(encoding="utf-8")]
con = sqlite3.connect(ROOT / ".cache" / "db-v2.sqlite")
con.text_factory = lambda b: b.decode("utf-8", "replace")
have2 = {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}

tr = [o for o in rows if o["trail"]]
gp = [o for o in rows if o["gap"]]
nvT = sum(len(o["trail"]) for o in tr)
nvG = sum(len(o["gap"]) for o in gp)
s2T = sum(1 for o in tr for c in o["trail"] if str(c["isbn"]) in have2)
s2G = sum(1 for o in gp for c in o["gap"] if str(c["isbn"]) in have2)
both = len({o["slug"] for o in tr} & {o["slug"] for o in gp})

print(f"★完走 {len(rows):,}作")
print(f"  末尾続刊 TRAIL : {len(tr):,}作 / {nvT:,}巻  (種2に在る {s2T:,}巻=誤配属型 / 無い {nvT - s2T:,}巻=種4)")
print(f"  途中欠番 GAP   : {len(gp):,}作 / {nvG:,}巻  (種2に在る {s2G:,}巻=誤配属型 / 無い {nvG - s2G:,}巻=種4)")
print(f"  両方あり       : {both:,}作")
print(f"  truncated(楽天30件上限) : {sum(1 for o in rows if o['truncated']):,}作 ← 欠番検出が不完全")

p = ROOT / "docs" / "production-diagnostics" / "recent-ongoing-volumes.tsv"
with io.open(p, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["kind", "slug", "title", "our_max", "our_nvols", "miss_vol", "isbn", "date", "in_seed2", "truncated"])
    for o in rows:
        for kind, key in (("TRAIL", "trail"), ("GAP", "gap")):
            for c in sorted(o[key], key=lambda c: c["vol"]):
                w.writerow([kind, o["slug"], o["title"], o["our_max"], len(o["our_vols"]), c["vol"],
                            c["isbn"], c["date"], "Y" if str(c["isbn"]) in have2 else "",
                            "Y" if o["truncated"] else ""])
print(f"→ {p}")

print("\n■末尾続刊が多い順 上位12:")
for o in sorted(tr, key=lambda o: -len(o["trail"]))[:12]:
    b = max(o["trail"], key=lambda c: c["vol"])
    print(f"   +{len(o['trail']):>2}巻  当方{o['our_max']:>3}→{b['vol']:>3}  {o['title'][:28]:30s} 最新{b['date']}")
print("\n■欠番が多い順 上位10:")
for o in sorted(gp, key=lambda o: -len(o["gap"]))[:10]:
    print(f"   欠{len(o['gap']):>2}巻  {o['title'][:28]:30s} 欠番={[c['vol'] for c in o['gap'][:10]]}")
