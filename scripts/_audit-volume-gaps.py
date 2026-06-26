"""巻数抜け(巻番号の欠番)を検出(調査リスト作成のみ・変更なし)。standard版の巻番号1..maxで欠番=取りこぼし候補。"""
import yaml, json, os, csv
ROOT = "C:/Users/shuic/code/MANGAL"
raw = json.load(open(ROOT + "/data/manga-list-index.json", encoding="utf-8"))
f = raw["f"]; si = f.index("slug"); tvi = f.index("total_volumes")
targets = [r[si] for r in raw["d"] if (r[tvi] or 0) >= 3]
print(f"対象(総巻数>=3): {len(targets)}件 をスキャン", flush=True)
rows = []
for n, sl in enumerate(targets):
    if n % 2000 == 0: print(f"  ...{n}/{len(targets)}", flush=True)
    p = ROOT + "/data/manga.v2/" + sl + ".yml"
    if not os.path.exists(p): continue
    try: d = yaml.safe_load(open(p, encoding="utf-8"))
    except: continue
    if not d: continue
    for ed in (d.get("editions") or []):
        if ed.get("type") != "standard": continue
        nums = set()
        for v in (ed.get("volumes") or []):
            nm = v.get("number")
            if isinstance(nm, (int, float)) and nm == int(nm) and nm >= 1: nums.add(int(nm))
        if len(nums) < 2: break
        mx = max(nums); have = len(nums)
        missing = [k for k in range(1, mx + 1) if k not in nums]
        if missing:
            rows.append({"slug": d["slug"], "title": str(d.get("title"))[:28], "have": have, "max": mx,
                         "miss": len(missing), "ratio": round(have / mx, 2),
                         "missing": ",".join(map(str, missing[:15])) + ("…" if len(missing) > 15 else "")})
        break
rows.sort(key=lambda x: (-x["ratio"], -x["max"]))
with open(ROOT + "/docs/volume-gaps.tsv", "w", encoding="utf-8", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=["slug","title","have","max","miss","ratio","missing"], delimiter="\t")
    w.writeheader(); w.writerows(rows)
print(f"\n巻数抜けあり: {len(rows)}件 -> docs/volume-gaps.tsv", flush=True)
near = [r for r in rows if r["ratio"] >= 0.8 and r["max"] >= 5]
print(f"  ほぼ完備(ratio>=0.8 & max>=5): {len(near)}件", flush=True)
print("\n=== ほぼ完備で欠番(取りこぼし濃厚) Top25 ===", flush=True)
for r in near[:25]:
    print(f"  [{r['have']}/{r['max']}巻 欠{r['miss']}] {r['slug'][:32]} 欠番={r['missing']}", flush=True)
