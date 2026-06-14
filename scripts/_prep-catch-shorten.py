"""80字超のキャッチだけ短縮するための作業リスト生成。
catch-ja.json から len>80 を抽出 → 各slugの title/synopsis を data/manga.v2 から引く
→ 75件/batch で .cache/catch-short-batches/ に出力(slug\\ttitle\\tsynopsis\\tcurrent)。"""
import os, json, io, glob, yaml, shutil

THRESH = 80
PER = 75
SRC = "data/manga.v2"
BD = ".cache/catch-short-batches"

catch = json.load(io.open("data/seeds/catch-ja.json", encoding="utf-8"))
over = {s: c for s, c in catch.items() if len(c) > THRESH}
print(f"{THRESH}字超 = {len(over)} 件")

# 該当slugの title/synopsis を取得(該当ファイルのみ読む=軽量)
rows = []
miss = 0
for slug, cur in over.items():
    p = os.path.join(SRC, slug + ".yml")
    title = ""
    syn = ""
    if os.path.exists(p):
        try:
            d = yaml.safe_load(io.open(p, encoding="utf-8"))
            title = d.get("title", "")
            syn = (d.get("synopsis") or "").replace("\t", " ").replace("\n", " ")
        except Exception:
            pass
    else:
        miss += 1
    rows.append((slug, title, syn, cur.replace("\t", " ")))

if os.path.isdir(BD):
    shutil.rmtree(BD)
os.makedirs(BD, exist_ok=True)
n = 0
for i in range(0, len(rows), PER):
    n += 1
    with io.open(os.path.join(BD, f"b-{n:04d}.tsv"), "w", encoding="utf-8") as w:
        for slug, title, syn, cur in rows[i:i + PER]:
            w.write(f"{slug}\t{title}\t{syn}\t{cur}\n")
print(f"batches={n} (各{PER}) / v2不在={miss} / dir={BD}")
