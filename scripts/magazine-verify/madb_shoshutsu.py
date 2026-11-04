"""MADB cm101/cm104 の「初出」記載を1パスで抜く(読むだけ)。
出力 .cache/magazine-lists/madb-shoshutsu.jsonl = {mid, isbn, series(C-id), title, vol, pub, brand, date, src(dataPublisher), text}
"""
import ijson, json, sys
sys.stdout.reconfigure(encoding="utf-8")
OUT = open(".cache/magazine-lists/madb-shoshutsu.jsonl", "w", encoding="utf-8")

def s(v):
    if isinstance(v, list):
        v = next((x for x in v if isinstance(x, str)), "")
    if isinstance(v, dict):
        return v.get("@id") or v.get("@value") or ""
    return v or ""

n = hit = 0
for fn, kind in ((".cache/madb/metadata101.json", "book"), (".cache/madb/metadata104.json", "series")):
    with open(fn, "rb") as f:
        for r in ijson.items(f, "@graph.item"):
            n += 1
            texts = []
            for k in ("schema:description", "ma:note"):
                v = r.get(k)
                for x in (v if isinstance(v, list) else [v]):
                    if isinstance(x, str) and "初出" in x:
                        texts.append(x)
            if not texts:
                continue
            hit += 1
            OUT.write(json.dumps({"kind": kind, "mid": r.get("schema:identifier"), "isbn": s(r.get("schema:isbn")),
                                  "series": s(r.get("schema:isPartOf")), "title": s(r.get("schema:name")),
                                  "vol": s(r.get("schema:volumeNumber")), "pub": s(r.get("schema:publisher")),
                                  "brand": s(r.get("schema:brand")), "date": s(r.get("schema:datePublished")),
                                  "src": s(r.get("ma:dataPublisher")), "text": " / ".join(texts)}, ensure_ascii=False) + "\n")
print("records", n, "初出あり", hit)
