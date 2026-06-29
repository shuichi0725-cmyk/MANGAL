"""教育系で年代版混入(1edition内に複数ISBN発行コード=別年版が混ざる)を検出。日本の歴史型の横展開対象を洗い出す。"""
import json, yaml, re, os, collections

ROOT = "C:/Users/shuic/code/MANGAL"
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
fi = {k: i for i, k in enumerate(idx["f"])}
EDU = re.compile(r"世界の歴史|日本の歴史|まんが日本|歴史人物|伝記|偉人|学習まんが|学習漫画|学研まんが|科学|サバイバル|図鑑|大百科|ことわざ|四字熟語|百人一首|古典|名作|ひみつ|なぜ|物語|大戦|文明")

def codeof(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    return ib[6:10] if len(ib) == 13 else None

def yr(s):
    m = re.match(r"(\d{4})", str(s or ""))
    return int(m.group(1)) if m else None

cands = []
for r in idx["d"]:
    if r[fi["demographic"]] != "kodomo" or not (EDU.search(r[fi["title"]] or "") or "historical" in (r[fi["genres"]] or [])):
        continue
    sl = r[fi["slug"]]
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for e in d.get("editions", []):
        codes = collections.Counter()
        years = []
        for v in e.get("volumes", []):
            c = codeof(v.get("isbn13"))
            if c:
                codes[c] += 1
            y = yr(v.get("release_date"))
            if y:
                years.append(y)
        if len(codes) > 1 and years and (max(years) - min(years) >= 5):
            cands.append((sl, d.get("title", "")[:24], e.get("type"), dict(codes), min(years), max(years), len(e.get("volumes", []))))
            break

cands.sort(key=lambda x: -(x[5] - x[4]))
print(f"年代版混入の疑い(1edition内 複数コード×年幅5年+): {len(cands)}")
for sl, t, ty, codes, lo, hi, n in cands:
    print(f"  {t:24} [{ty}] {n}巻 年{lo}-{hi} コード{codes}")
json.dump([c[0] for c in cands], open(f"{ROOT}/.cache/edu-edition-mix-slugs.json", "w", encoding="utf-8"), ensure_ascii=False)
