"""MADB 雑誌掲載履歴(cm106) × 目次(108) × 雑誌各号(cm102) × 雑誌(cm105) を1パスずつで結ぶ(読むだけ)。
出力 .cache/magazine-lists/madb-serial.jsonl = 掲載履歴1件ごとに {cid, name, kana, creators, start, mags:[[誌名, 回数, 初回日付]...]}"""
import ijson, json, sys
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding="utf-8")
X = ".cache/madb-extra"

def ids(v):
    if isinstance(v, dict): return v.get("@id", "").rsplit("/", 1)[-1]
    if isinstance(v, list): return ids(v[0]) if v else ""
    return (v or "").rsplit("/", 1)[-1]

def names(v):
    out = []
    for x in (v if isinstance(v, list) else [v]):
        if isinstance(x, str): out.append(x)
    return out

def kana(v):
    for x in (v if isinstance(v, list) else [v]):
        if isinstance(x, dict) and x.get("@language") == "ja-hrkt": return x.get("@value", "")
    return ""

magname = {}
with open(".cache/madb/metadata105.json", "rb") as f:
    for r in ijson.items(f, "@graph.item"):
        magname[r["schema:identifier"]] = (names(r.get("schema:name")) or [r.get("rdfs:label", "")])[0]
issue = {}
with open(f"{X}/m102/metadata102.json", "rb") as f:
    for r in ijson.items(f, "@graph.item"):
        issue[r["schema:identifier"]] = (ids(r.get("schema:isPartOf")), str(r.get("schema:datePublished") or r.get("ma:yearDisplayed") or ""))
print("雑誌", len(magname), "号", len(issue), file=sys.stderr)
agg = defaultdict(lambda: defaultdict(lambda: [0, "9999"]))
n = genres = 0; gc = Counter()
with open(f"{X}/m108/metadata108.json", "rb") as f:
    for r in ijson.items(f, "@graph.item"):
        n += 1
        g = r.get("schema:genre") or ""
        gc[g] += 1
        if g != "マンガ作品":
            continue
        coll = ids(r.get("ma:relatedCollectionOfManga")); iss = ids(r.get("ma:relatedCollectionOfMagazine"))
        if not coll or iss not in issue:
            continue
        mag, date = issue[iss]
        a = agg[coll][mag]; a[0] += 1
        if date and date < a[1]: a[1] = date
print("目次", n, gc.most_common(8), "作品つき掲載履歴", len(agg), file=sys.stderr)
out = open(".cache/magazine-lists/madb-serial.jsonl", "w", encoding="utf-8")
m = 0
with open(f"{X}/m106/metadata106.json", "rb") as f:
    for r in ijson.items(f, "@graph.item"):
        cid = r["schema:identifier"]
        mags = sorted(([magname.get(k, k), v[0], v[1]] for k, v in agg.get(cid, {}).items()), key=lambda x: x[2])
        m += bool(mags)
        out.write(json.dumps({"cid": cid, "name": (names(r.get("schema:name")) or [r.get("rdfs:label", "")])[0], "kana": kana(r.get("schema:name")),
                              "creators": names(r.get("schema:creator")) + names(r.get("ma:originalWorkCreator")),
                              "start": str(r.get("schema:datePublished") or ""), "note": r.get("ma:note") or "", "mags": mags}, ensure_ascii=False) + "\n")
print("掲載履歴の書き出し(誌が分かる)", m, file=sys.stderr)
