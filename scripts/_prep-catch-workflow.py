"""キャッチ生成ワークフローの前処理: data/manga.v2 から あらすじ有 かつ
catch-ja.json 未生成 の作品を人気順で抽出し、 75件/バッチで .cache/catch-batches/ に分割。
各バッチ = b-NNNN.tsv(ヘッダ無し, slug\\ttitle\\tgenres\\tsynopsis)。 バッチ数を出力。"""
import os, glob, json, yaml, shutil

SRC = "data/manga.v2"
BATCH_DIR = ".cache/catch-batches"
PER = 75

existing = {}
if os.path.exists("data/seeds/catch-ja.json"):
    existing = json.load(open("data/seeds/catch-ja.json", encoding="utf-8"))

rows = []
for f in glob.glob(os.path.join(SRC, "*.yml")):
    try:
        d = yaml.safe_load(open(f, encoding="utf-8"))
    except Exception:
        continue
    syn = (d.get("synopsis") or "").strip()
    if not syn:
        continue
    slug = d.get("slug") or os.path.splitext(os.path.basename(f))[0]
    if slug in existing:
        continue
    rows.append((d.get("popularity") or 0, slug, d.get("title", ""),
                 ",".join(d.get("genres") or []), syn.replace("\t", " ").replace("\n", " ")))

rows.sort(key=lambda r: r[0], reverse=True)

if os.path.isdir(BATCH_DIR):
    shutil.rmtree(BATCH_DIR)
os.makedirs(BATCH_DIR, exist_ok=True)

n_batches = 0
for i in range(0, len(rows), PER):
    n_batches += 1
    chunk = rows[i:i + PER]
    with open(os.path.join(BATCH_DIR, f"b-{n_batches:04d}.tsv"), "w", encoding="utf-8") as w:
        for pop, slug, title, genres, syn in chunk:
            w.write(f"{slug}\t{title}\t{genres}\t{syn}\n")

print(f"todo={len(rows)} / batches={n_batches} (各{PER}件) / dir={BATCH_DIR}")
