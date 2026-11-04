"""第2弾(ユーザ「残り約130誌を足して60頁と194頁を直して」): 段階 A・B・D で、 正しい誌がマスタに無いため
直せなかった頁(誤った値が残る / 空欄のまま)が指す誌を、 誌ごとにまとめる(読むだけ)。
出力 .cache/magazine-lists/missing-mags-2.json = {canon: {names, pages:[slug..], wrong, empty, pubs(頁の出版社), cm105:[...]}}"""
import csv, json, os, sys, re
from collections import Counter, defaultdict
import ijson, yaml

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from wiki_mag_lib import ROOT, canon
import madb_apply as A
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache", "magazine-lists")
mags = yaml.safe_load(open(os.path.join(ROOT, "data", "magazines.yml"), encoding="utf-8"))
corr = yaml.safe_load(open(os.path.join(ROOT, "data", "seeds", "magazine-corrections.yml"), encoding="utf-8"))["corrections"]
li = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8")); F = {k: i for i, k in enumerate(li["f"])}
P = {r[F["slug"]]: r for r in li["d"]}
judge = {x["slug"]: x for x in json.load(open(os.path.join(L, "wiki-judge2.json"), encoding="utf-8"))}

cm105 = defaultdict(list)
with open(os.path.join(ROOT, ".cache", "madb", "metadata105.json"), "rb") as f:
    for r in ijson.items(f, "@graph.item"):
        nm = r.get("schema:name"); nm = nm if isinstance(nm, list) else [nm]
        name = next((x for x in nm if isinstance(x, str)), r.get("rdfs:label", ""))
        pub = r.get("schema:publisher"); pub = pub[0] if isinstance(pub, list) else pub
        cm105[canon(name)].append({"name": name, "pub": (pub or "").split("　∥")[0].strip(), "period": r.get("ma:publicationPeriodicity", ""),
                                   "start": str(r.get("schema:datePublished", ""))[:10], "end": str(r.get("ma:dayPublishedFinal", ""))[:10],
                                   "id": r.get("schema:identifier")})

out = defaultdict(lambda: {"names": Counter(), "pages": [], "wrong": 0, "empty": 0, "pubs": Counter(), "demo": Counter()})
skip = Counter()
for r in csv.DictReader((ln for ln in open(A.TSV, encoding="utf-8") if not ln.startswith("#")), delimiter="\t"):
    t = r["段階"][0]
    if t not in "ABD" or r["slug"] in corr:
        continue
    zoukan = t in "AB" and A.PURE_ZOUKAN.match(r["MADB誌名"] or "")
    tgt = A.target_of(r["提案"], mags)
    if tgt and not zoukan:
        continue                                   # 第1弾で直した(または直せる)頁
    if not r["提案"]:
        skip["提案が空(複数誌=空のまま)"] += 1; continue
    if zoukan:
        name = r["MADB誌名"]                       # ★「Sho-Comi増刊」等 = 増刊は別の誌(ユーザ裁定3)
    else:
        name = r["提案"][1:] if r["提案"].startswith("?") else r["提案"]
    x = judge.get(r["slug"], {})
    raw = [name]
    if x.get("madb") and not zoukan:
        raw.append(x["madb"])
    w = x.get("wiki") or {}
    if w.get("name") and w.get("id", "").lstrip("?") == canon(name):
        raw.append(w["name"])
    c = canon(name)
    o = out[c]
    for n in raw:
        if n and not n.startswith("?"):
            o["names"][n] += 1
    o["pages"].append(r["slug"])
    o["wrong" if r["今の連載誌"] else "empty"] += 1
    p = P.get(r["slug"])
    if p:
        o["pubs"][p[F["publisher"]] or ""] += 1
        o["demo"][p[F["demographic"]] or ""] += 1
res = {}
for c, o in out.items():
    info = cm105.get(c) or []
    res[c] = {"names": o["names"].most_common(), "pages": o["pages"], "wrong": o["wrong"], "empty": o["empty"],
              "pubs": o["pubs"].most_common(3), "demo": o["demo"].most_common(3), "cm105": info[:3]}
json.dump(res, open(os.path.join(L, "missing-mags-2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("誌", len(res), "/ 頁", sum(len(v["pages"]) for v in res.values()), "(誤り", sum(v["wrong"] for v in res.values()), "空欄", sum(v["empty"] for v in res.values()), ")", "/ 外した", dict(skip))
for c, v in sorted(res.items(), key=lambda kv: -len(kv[1]["pages"])):
    cm = v["cm105"][0] if v["cm105"] else {}
    print(f'{len(v["pages"]):3d} 誤{v["wrong"]} 空{v["empty"]} | {v["names"][0][0] if v["names"] else c} | 別表記 {[n for n, _ in v["names"][1:3]]} | 頁の出版社 {v["pubs"][:2]} | MADB {cm.get("pub", "")} {cm.get("start", "")}〜{cm.get("end", "")}')
