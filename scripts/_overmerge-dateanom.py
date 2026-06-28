"""過剰統合の高確度検出: 単一edition内でISBN出版社prefix混在 かつ 少数派prefix巻の発売日が
主prefixの年範囲外(=別シリーズの混入signal、 世界の歴史型)。 これが確証ある over-merge 候補。"""
import json, yaml, re, os

ROOT = "C:/Users/shuic/code/MANGAL"

def registrant(isbn):
    if not isbn.startswith("9784") or len(isbn) != 13:
        return None
    b = isbn[4:12]; n2 = int(b[:2])
    return b[:2] if n2 <= 19 else b[:3] if n2 <= 69 else b[:4] if n2 <= 84 else b[:5] if n2 <= 89 else b[:6] if n2 <= 94 else b[:7]

def yr(s):
    m = re.match(r"(\d{4})", str(s or ""))
    return int(m.group(1)) if m else None

cand = json.load(open(f"{ROOT}/.cache/single-edition-mix.json", encoding="utf-8"))
strong = []
for c in cand:
    p = f"{ROOT}/data/manga.v2/{c['slug']}.yml"
    if not os.path.exists(p):
        continue
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for e in d.get("editions", []):
        if e.get("type") != c["edition"]:
            continue
        vols = []
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            vols.append((v.get("number"), registrant(ib), yr(v.get("release_date")), ib))
        mainyrs = [y for n, r, y, ib in vols if r == c["top"] and y]
        if not mainyrs:
            break
        lo, hi = min(mainyrs), max(mainyrs)
        intruders = [(n, r, y, ib) for n, r, y, ib in vols if r and r != c["top"] and y and (y < lo - 1 or y > hi + 1)]
        if intruders:
            strong.append({"slug": c["slug"], "title": d.get("title", "")[:28],
                           "main_prefix": c["top"], "main_years": [lo, hi],
                           "intruders": [{"number": n, "prefix": r, "year": y, "isbn": ib} for n, r, y, ib in intruders]})
        break

print(f"高確度(prefix混在+発売日が主範囲外)= 過剰統合強疑い: {len(strong)}")
strong.sort(key=lambda x: x["title"])
for s in strong[:40]:
    intr = [(i["number"], i["prefix"], i["year"]) for i in s["intruders"]]
    print(f"  {s['title']:30} 主{s['main_prefix']}({s['main_years'][0]}-{s['main_years'][1]}) 混入{intr}")
json.dump(strong, open(f"{ROOT}/.cache/overmerge-strong.json", "w", encoding="utf-8"), ensure_ascii=False)
print("→ .cache/overmerge-strong.json")
