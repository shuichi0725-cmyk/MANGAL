"""(2)非教育系の1版内prefix混在を特性分析。 各作: 混在パターンが
 ①重複番号(1,1,2,2)=多版を1edition に平坦化 ②連番だが途中でprefix変化=版混在/過剰統合 ③その他。
キー=マンガ名+作者。 アンソロ除外。 版分離が必要な規模を把握。"""
import json, yaml, re, os, collections, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
cand = json.load(open(f"{ROOT}/.cache/single-edition-mix.json", encoding="utf-8"))
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
fi = {k: i for i, k in enumerate(idx["f"])}
EDU = re.compile(r"世界の歴史|日本の歴史|まんが日本|歴史人物|伝記|偉人|学習まんが|学習漫画|学研まんが")
edu = {r[fi["slug"]] for r in idx["d"] if r[fi["demographic"]] == "kodomo" and (EDU.search(r[fi["title"]] or "") or "historical" in (r[fi["genres"]] or []))}
ANTH = re.compile(r"アンソロジー|傑作選|名作選|セレクション|競作")

def reg(i):
    if not i.startswith("9784") or len(i) != 13:
        return None
    b = i[4:12]; n = int(b[:2])
    return b[:2] if n <= 19 else b[:3] if n <= 69 else b[:4] if n <= 84 else b[:5] if n <= 89 else b[:6] if n <= 94 else b[:7]

dup_pat = []     # 重複番号(多版平坦化)
consec_pat = []  # 連番でprefix変化(版混在/過剰統合疑い)
other = []
for c in cand:
    sl = c["slug"]
    if sl in edu:
        continue
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    if ANTH.search(d.get("title", "")):
        continue
    for e in d.get("editions", []):
        if e.get("type") != c["edition"]:
            continue
        nums = [v.get("number") for v in e.get("volumes", [])]
        byreg = collections.defaultdict(list)
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or "")); r = reg(ib)
            if r:
                byreg[r].append(v.get("number"))
        dup = len(nums) - len(set(nums))
        rec = (sl, d.get("title", "")[:24], {k: sorted(set(v)) for k, v in byreg.items()}, dup)
        if dup > 0:
            dup_pat.append(rec)
        else:
            consec_pat.append(rec)
        break

print(f"非教育 1版内prefix混在: 重複番号型(多版平坦化)={len(dup_pat)} / 連番prefix変化型={len(consec_pat)}")
print("\n=== 重複番号型(=多版を1版に平坦化・版分離候補) サンプル ===")
for sl, t, br, dup in dup_pat[:15]:
    print(f"  {t:22} 重複{dup} prefix別{ {k: (v[:3], '...' if len(v) > 3 else '') for k, v in br.items()} }")
print("\n=== 連番prefix変化型(=途中で出版社変化=版混在/要精査) サンプル ===")
for sl, t, br, dup in consec_pat[:20]:
    print(f"  {t:22} {br}")
json.dump({"dup": dup_pat, "consec": consec_pat}, open(f"{ROOT}/.cache/overmerge2-investigate.json", "w", encoding="utf-8"), ensure_ascii=False)
