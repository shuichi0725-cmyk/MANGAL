"""マスターに無い誌の集計: 裁定表(wiki-judge2.json)で 「Wiki+MADB 一致」 or 「MADBのみ(強)」 の頁が指す誌を
誌ごとに数え、 MADB cm105 の出版社・刊行頻度・創刊/終刊 を添える(読むだけ)。"""
import json, sys, os, re, ijson
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from wiki_mag_lib import ROOT, canon, ident
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache/magazine-lists")
res = json.load(open(f"{L}/wiki-judge2.json", encoding="utf-8"))
cm105 = defaultdict(list)
with open(os.path.join(ROOT, ".cache/madb/metadata105.json"), "rb") as f:
    for r in ijson.items(f, "@graph.item"):
        nm = r.get("schema:name"); nm = nm if isinstance(nm, list) else [nm]
        name = next((x for x in nm if isinstance(x, str)), r.get("rdfs:label", ""))
        pub = r.get("schema:publisher"); pub = pub[0] if isinstance(pub, list) else pub
        cm105[canon(name)].append({"name": name, "pub": (pub or "").split("　∥")[0], "period": r.get("ma:publicationPeriodicity", ""),
                                   "start": r.get("schema:datePublished", ""), "end": r.get("ma:dayPublishedFinal", "")})
agg = defaultdict(lambda: {"names": Counter(), "ok": 0, "madb_only": 0, "review": 0, "ex": []})
for x in res:
    w = x["wiki"]; v = x["verdict"]
    if v.startswith(("直す(Wiki+MADB)", "埋める(Wiki+MADB)", "直す(MADB+楽天)", "埋める(MADB+楽天)")):
        mid = x["madb_id"]; kind = "ok"
    elif v.startswith("MADBのみ(強)"):
        mid = x["madb_id"]; kind = "madb_only"
    elif v.startswith("要確認") and w and w["id"].startswith("?"):
        mid = w["id"]; kind = "review"
    else:
        continue
    if not mid.startswith("?"):
        continue
    a = agg[mid]
    a["names"][x["madb"] if kind != "review" else w["name"]] += 1
    if w and w["id"] == mid:
        a["names"][w["name"]] += 1
    a[kind] += 1
    if len(a["ex"]) < 4:
        a["ex"].append(x["title"])
rows = []
for mid, a in agg.items():
    info = cm105.get(mid[1:]) or []
    if not info:
        for k, v in cm105.items():
            if len(k) >= 4 and (k == mid[1:] or (mid[1:] in k and len(k) - len(mid[1:]) <= 2)):
                info = v; break
    i0 = info[0] if info else {}
    rows.append((a["ok"] + a["madb_only"], a["ok"], a["madb_only"], a["review"], a["names"].most_common(1)[0][0],
                 "/".join(n for n, _ in a["names"].most_common(3)[1:]), i0.get("pub", ""), i0.get("period", ""),
                 str(i0.get("start", ""))[:10], str(i0.get("end", ""))[:10], "・".join(a["ex"])))
rows.sort(key=lambda r: -r[0])
with open(f"{L}/master-missing-mags.tsv", "w", encoding="utf-8") as f:
    f.write("頁計\tWiki+MADB一致\tMADBのみ強\t要確認\t誌名\t別表記\t出版社(MADB)\t刊行\t創刊\t終刊\t例\n")
    for r in rows:
        f.write("\t".join(str(x) for x in r) + "\n")
print("誌の数", len(rows), "/ 頁計", sum(r[0] for r in rows))
for r in rows[:45]:
    print(f"  {r[0]:4d} (一致{r[1]} MADBのみ{r[2]} 要確認{r[3]}) {r[4]} [{r[5]}] {r[6]} {r[7]} {r[8]}〜{r[9]} 例:{r[10][:40]}")
