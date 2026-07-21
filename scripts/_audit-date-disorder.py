"""発売日と巻番号の順番が矛盾するページを検出(調査リスト作成のみ・変更なし)。
standard版で巻番号順に並べた時、発売日が逆行する箇所=汚染(別作/別版の混入)の候補。長期連載優先。"""
import yaml, json, os, csv, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
raw = json.load(open(ROOT + "/data/manga-list-index.json", encoding="utf-8"))
f = raw["f"]; si = f.index("slug"); tvi = f.index("total_volumes")
longs = [r[si] for r in raw["d"] if (r[tvi] or 0) >= 10]
print(f"長期連載(総巻数>=10): {len(longs)}件 をスキャン", flush=True)
def yr(s): return int(s[:4]) if s[:4].isdigit() else 0
rows = []
for n, sl in enumerate(longs):
    if n % 1000 == 0: print(f"  ...{n}/{len(longs)}", flush=True)
    p = ROOT + "/data/manga.v2/" + sl + ".yml"
    if not os.path.exists(p): continue
    try: d = yaml.safe_load(open(p, encoding="utf-8"))
    except: continue
    if not d: continue
    for ed in (d.get("editions") or []):
        if ed.get("type") != "standard": continue
        vols = [(v.get("number"), str(v.get("release_date") or ""), v.get("isbn13"))
                for v in (ed.get("volumes") or []) if v.get("number") and v.get("release_date")]
        if len(vols) < 5: break
        vols.sort(key=lambda x: x[0])
        bad = []
        for i in range(1, len(vols)):
            if vols[i][1] and vols[i-1][1] and vols[i][1] < vols[i-1][1]:
                bad.append((vols[i-1][0], vols[i-1][1], vols[i][0], vols[i][1], vols[i][2]))
        if bad:
            worst = max(bad, key=lambda b: abs(yr(b[1]) - yr(b[3])))
            gap = abs(yr(worst[1]) - yr(worst[3]))
            rows.append({"slug": d["slug"], "title": str(d.get("title"))[:28], "vols": len(vols),
                         "inv": len(bad), "gap_yr": gap,
                         "worst": f"#{worst[0]}({worst[1][:7]})->#{worst[2]}({worst[3][:7]})", "bad_isbn": worst[4] or ""})
        break
rows.sort(key=lambda x: (-x["gap_yr"], -x["vols"]))
with open(ROOT + "/docs/volume-date-disorder.tsv", "w", encoding="utf-8", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=["slug", "title", "vols", "inv", "gap_yr", "worst", "bad_isbn"], delimiter="\t")
    w.writeheader(); w.writerows(rows)
print(f"\n発売日逆行あり: {len(rows)}件 -> docs/volume-date-disorder.tsv", flush=True)
print("\n=== 逆行幅(年)大きい順 Top25 ===", flush=True)
for r in rows[:25]:
    print(f"  [{r['gap_yr']}yr/{r['vols']}巻/逆{r['inv']}] {r['slug'][:34]} {r['worst']}", flush=True)
golgo = [r for r in rows if "golgo" in r["slug"] or "ゴルゴ" in r["title"]]
print("\n=== ゴルゴ13系 ===", flush=True)
for r in golgo: print(f"  {r['slug']} {r['vols']}巻 逆{r['inv']} {r['worst']}", flush=True)
