"""MADB 掲載履歴(目次由来) × 本番頁: 題(正規化一致)+著者+年 で突き合わせ、 今の連載誌と比べる(読むだけ)。"""
import json, re, sys, unicodedata, csv, yaml
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
D = ".cache/magazine-lists"
TR = re.compile(r"[\s・･!！?？。、,，.．:：;；\"'“”‘’「」『』()（）\[\]［］〜~\-‐－—―=＝/／★☆♪♡♥❤＋+×&＆]")
def norm(s): return TR.sub("", unicodedata.normalize("NFKC", s or "").lower())
def tkeys(t):
    k = {norm(t), norm(re.sub(r"[(（][^)）]*[)）]", "", t)), norm(re.split(r"[ 　]+[-‐－〜~]", t)[0])}
    return {x for x in k if len(x) >= 2}
def akey(a):
    a = re.sub(r"\[[^\]]*\]|［[^］]*］|【[^】]*】", "", a)        # [作] [画] 等の役割札
    return norm(a)

MAGMAP = {"週刊少年ジャンプ": "weekly-shonen-jump", "少年ジャンプ": "weekly-shonen-jump", "週刊少年マガジン": "weekly-shonen-magazine",
          "週刊少年サンデー": "weekly-shonen-sunday", "週刊少年チャンピオン": "champion", "少年チャンピオン": "champion",
          "花とゆめ": "hana-to-yume", "なかよし": "nakayoshi", "りぼん": "ribon", "ちゃお": "ciao", "ビッグコミック": "big-comic",
          "週刊漫画アクション": "manga-action", "グランドジャンプ": "grand-jump", "ジャンプSQ.": "jump-sq"}
li = json.load(open("data/manga-list-index.json", encoding="utf-8"))
F = {k: i for i, k in enumerate(li["f"])}
def nm(v): return [str(x).split("\t")[0] if not isinstance(x, dict) else x.get("name", "") for x in (v or [])]
pages = [{"slug": r[F["slug"]], "title": r[F["title"]], "mag": r[F["magazine"]] or "", "pub": r[F["publisher"]] or "",
          "year": r[F["year_started"]] or 0, "authors": [a for a in nm(r[F["authors"]]) + nm(r[F["original_authors"]]) if a]} for r in li["d"]]
by_t = defaultdict(list)
for p in pages:
    for k in tkeys(p["title"]): by_t[k].append(p)

fixed = {json.loads(l)["slug"] for l in open("data/seeds/magazine-fix-changelog.jsonl", encoding="utf-8")}
unres = {r["slug"]: r for r in csv.DictReader(open("docs/production-diagnostics/magazine-unresolved-2026-11-04.tsv", encoding="utf-8"), delimiter="\t")}

hits = defaultdict(list)
for l in open(f"{D}/madb-serial.jsonl", encoding="utf-8"):
    s = json.loads(l)
    if not s["mags"]: continue
    aks = {akey(a) for a in s["creators"] if len(akey(a)) >= 2}
    if not aks: continue
    y0 = int(s["mags"][0][2][:4]) if s["mags"][0][2][:4].isdigit() else 0
    cand = {id(p): p for k in tkeys(s["name"]) for p in by_t.get(k, [])}
    for p in cand.values():
        pa = {akey(a) for a in p["authors"]}
        if not any(a in b or b in a for a in aks for b in pa if len(b) >= 2): continue
        if p["year"] and y0 and not (y0 - 1 <= p["year"] <= y0 + 4): continue
        hits[p["slug"]].append(s)

res = []; cls_c = Counter()
for slug, ss in hits.items():
    p = next(x for x in by_t[next(iter(tkeys(next(pp["title"] for pp in pages if pp["slug"] == slug))))] if x["slug"] == slug) if False else None
pmap = {p["slug"]: p for p in pages}
for slug, ss in hits.items():
    p = pmap[slug]
    tot = Counter(); first = {}
    for s in ss:
        for name, n, d in s["mags"]:
            tot[name] += n
            if name not in first or d < first[name]: first[name] = d
    main, n_main = tot.most_common(1)[0]
    earliest = min(first, key=lambda k: first[k])
    key = MAGMAP.get(main, "")
    note = []
    if earliest != main and tot[earliest] >= 3: note.append(f"初出は{earliest}({tot[earliest]}回)")
    if len([m for m, n in tot.items() if n >= 3]) >= 2: note.append("複数誌に3回以上")
    if not key: cls = "マスタに無い誌"
    elif not p["mag"]: cls = "空欄→埋められる"
    elif p["mag"] == key: cls = "一致"
    else: cls = "食い違い"
    grp = "是正736" if slug in fixed else ("未解決表" if slug in unres else "その他")
    cls_c[(grp, cls, bool(note))] += 1
    res.append({"slug": slug, "title": p["title"], "cur": p["mag"], "madb": main, "key": key, "n": n_main, "mags": dict(tot), "first": first[main],
                "note": " / ".join(note), "grp": grp, "cls": cls, "unres_kind": unres.get(slug, {}).get("区分", ""), "pyear": p["year"]})
json.dump(res, open(f"{D}/madb-serial-vs-page.json", "w", encoding="utf-8"), ensure_ascii=False)
print("目次で連載誌が分かる頁", len(res))
for g in ("是正736", "未解決表", "その他"):
    print(g)
    for c in ("一致", "空欄→埋められる", "食い違い", "マスタに無い誌"):
        a, b = cls_c[(g, c, False)], cls_c[(g, c, True)]
        if a or b: print(f"   {c}: {a+b}(すっきり {a} / 移籍・複数誌の注意つき {b})")
print("マスタに無い誌:", Counter(x["madb"] for x in res if x["cls"] == "マスタに無い誌").most_common(15))
print("食い違い(今→MADB):", Counter((x["cur"], x["key"]) for x in res if x["cls"] == "食い違い").most_common(25))
