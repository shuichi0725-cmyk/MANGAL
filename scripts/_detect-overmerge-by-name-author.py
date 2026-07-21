"""(2)非教育系の過剰統合検出: prefix混在の少数派巻の実題名+著者(楽天)が本体と違う=別作の混入。
キー=マンガ名+作者(教育系のpublisher+labelとは別)。 アンソロジー除外。 確証=題名or著者の不一致。"""
import json, yaml, re, os, unicodedata, collections, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
APPLY = "--apply" in sys.argv
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))
tmap = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
cand = json.load(open(f"{ROOT}/.cache/single-edition-mix.json", encoding="utf-8"))

# 教育slug(除外) + index _anthology
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
fi = {k: i for i, k in enumerate(idx["f"])}
EDU = re.compile(r"世界の歴史|日本の歴史|まんが日本|歴史人物|伝記|偉人|学習まんが|学習漫画|学研まんが")
edu = set()
anth = set()
for r in idx["d"]:
    sl = r[fi["slug"]]
    if r[fi["demographic"]] == "kodomo" and (EDU.search(r[fi["title"]] or "") or "historical" in (r[fi["genres"]] or [])):
        edu.add(sl)
    if r[fi.get("_anthology", -1)] if "_anthology" in fi else False:
        anth.add(sl)

def reg(i):
    if not i.startswith("9784") or len(i) != 13:
        return None
    b = i[4:12]; n = int(b[:2])
    return b[:2] if n <= 19 else b[:3] if n <= 69 else b[:4] if n <= 84 else b[:5] if n <= 89 else b[:6] if n <= 94 else b[:7]

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

ANTH_T = re.compile(r"アンソロジー|傑作選|名作選|セレクション|競作|読切")
over = []   # (slug, title, vol, isbn, real_title, real_author, reason)
for c in cand:
    sl = c["slug"]
    if sl in edu or sl in anth:
        continue
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    if ANTH_T.search(d.get("title", "")):
        continue
    work_authors = [norm(a.get("name")) for a in (d.get("authors") or []) + (d.get("original_authors") or []) if a.get("name")]
    wt = norm(d.get("title", ""))
    if len(wt) < 2:
        continue
    for e in d.get("editions", []):
        if e.get("type") != c["edition"]:
            continue
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            if reg(ib) == c["top"] or not reg(ib):
                continue   # 少数派prefixのみ
            rt = tmap.get(ib, ""); ra = amap.get(ib, "")
            if not rt:
                continue   # 実題名不明=判定不能(慎重にskip)
            # 題名一致(本体題が実題名に含まれる) かつ 著者一致 → 同一作(版違い=keep)
            title_ok = wt in norm(rt)
            au_ok = any(wa and wa in norm(ra) for wa in work_authors) if (work_authors and ra) else False
            if not title_ok and not au_ok:
                over.append((sl, d.get("title", "")[:24], v.get("number"), ib, rt[:30], ra[:20]))
        break

print(f"(2)非教育 過剰統合(少数派巻の題名/著者が本体と不一致): {len(over)}")
for sl, t, num, ib, rt, ra in over[:35]:
    print(f"  {t:24} vol{num} → 実題[{rt}] 著[{ra}]")
json.dump(over, open(f"{ROOT}/.cache/overmerge2.json", "w", encoding="utf-8"), ensure_ascii=False)
