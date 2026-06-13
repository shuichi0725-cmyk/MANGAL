"""キャッチ生成の作業リスト: data/manga.v2 から slug/title/popularity/synopsis を抽出。
あらすじ(=確かな素材)があるものだけ対象(=「わからないのは埋めない」の機械的担保)。
人気順(降順)で並べ、 既に catch-ja.json にあるものは todo から除外。 .cache に出力。"""
import os, glob, json, yaml

SRC = "data/manga.v2"
OUT = ".cache/catch-worklist.tsv"
os.makedirs(".cache", exist_ok=True)

existing = {}
if os.path.exists("data/seeds/catch-ja.json"):
    existing = json.load(open("data/seeds/catch-ja.json", encoding="utf-8"))

rows = []
n_total = n_syn = 0
for f in glob.glob(os.path.join(SRC, "*.yml")):
    n_total += 1
    try:
        d = yaml.safe_load(open(f, encoding="utf-8"))
    except Exception:
        continue
    syn = (d.get("synopsis") or "").strip()
    if not syn:
        continue
    n_syn += 1
    slug = d.get("slug") or os.path.splitext(os.path.basename(f))[0]
    rows.append({
        "slug": slug,
        "title": d.get("title", ""),
        "pop": d.get("popularity") or 0,
        "genres": ",".join(d.get("genres") or []),
        "syn": syn.replace("\t", " ").replace("\n", " "),
        "done": slug in existing,
    })

rows.sort(key=lambda r: r["pop"], reverse=True)
todo = [r for r in rows if not r["done"]]
with open(OUT, "w", encoding="utf-8") as w:
    w.write("slug\tpop\ttitle\tgenres\tsynopsis\n")
    for r in todo:
        w.write(f"{r['slug']}\t{r['pop']}\t{r['title']}\t{r['genres']}\t{r['syn']}\n")

print(f"v2全件={n_total} / あらすじ有={n_syn} / 既catch={sum(1 for r in rows if r['done'])} / todo={len(todo)}")
print(f"todo上位pop: {[ (r['title'][:14], r['pop']) for r in todo[:5] ]}")
print(f"出力: {OUT}")
