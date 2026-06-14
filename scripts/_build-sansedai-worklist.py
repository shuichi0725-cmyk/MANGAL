"""三世代/今週ストック生成用の候補作リスト。 data/manga.v2 から人気上位を
slug/title/author/year/genres/demographic/popularity で抽出(TSV)。 人格AIがこの中から
作品を選んでコメントを書く(slugが実在ページに一致する保証)。"""
import os, glob, re, yaml

SRC = "data/manga.v2"
OUT = ".cache/sansedai-worklist.tsv"
TOP = 1800
os.makedirs(".cache", exist_ok=True)

# popularity 行を持つファイルだけ先に粗フィルタ(全66k件パースは遅いため)
POP_RE = re.compile(rb"^popularity:\s*[1-9]", re.M)
candidates = []
for f in glob.glob(os.path.join(SRC, "*.yml")):
    try:
        with open(f, "rb") as fh:
            if POP_RE.search(fh.read()):
                candidates.append(f)
    except Exception:
        continue

rows = []
for f in candidates:
    try:
        d = yaml.safe_load(open(f, encoding="utf-8"))
    except Exception:
        continue
    pop = d.get("popularity") or 0
    if not pop:
        continue
    slug = d.get("slug") or os.path.splitext(os.path.basename(f))[0]
    authors = "・".join(a.get("name", "") for a in (d.get("authors") or []) if a.get("name"))
    rows.append((pop, slug, d.get("title", ""), authors,
                 d.get("year_started") or "", ",".join(d.get("genres") or []),
                 d.get("demographic") or "", d.get("status") or ""))

rows.sort(reverse=True)
with open(OUT, "w", encoding="utf-8") as w:
    w.write("slug\ttitle\tauthor\tyear\tgenres\tdemographic\tstatus\n")
    for r in rows[:TOP]:
        w.write(f"{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}\t{r[6]}\t{r[7]}\n")
print(f"候補作 {min(len(rows),TOP)} 件 → {OUT} (全{len(rows)}件中の人気上位)")
