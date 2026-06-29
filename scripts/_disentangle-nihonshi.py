"""集英社 日本の歴史 の混入を ISBN発行コード(isbn[6:10])で年代版に分離。
2ページ(nihonnorekishi笠原 + 2007-2井上)は同じjumbleの重複→1ページに統合し、年代版を別editionタブに。
慎重: preview のみ・可逆(backup)・結果表示。 本番反映は確認後。"""
import yaml, re, os, json, collections, copy

ROOT = "C:/Users/shuic/code/MANGAL"
SRC = ["nihonnorekishi", "nippon-no-rekishi-2007-2"]
# 発行コード → (label, type)  ※集英社 日本の歴史の年代版
CODEMAP = {
    "2440": ("1982年版", "standard"),
    "1950": ("1992年版", "standard"), "1951": ("1992年版", "standard"),
    "2390": ("1998年版", "standard"),
    "7461": ("2007年版 漫画版(文庫)", "bunkobon"),
    "2391": ("2016年版 コンパクト", "standard"),
}

def code(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    return ib[6:10] if len(ib) == 13 else "?"

# 全巻収集(ISBN単位 dedup)
allvols = {}
for sl in SRC:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    d = yaml.safe_load(open(p, encoding="utf-8"))
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            if ib and ib not in allvols:
                allvols[ib] = v

# 発行コードでグループ → 年代版edition
byed = collections.defaultdict(list)
for ib, v in allvols.items():
    byed[code(ib)].append(v)

editions = []
order = ["2440", "1950", "1951", "2390", "7461", "2391"]
seen_label = {}
for c in order + [c for c in byed if c not in order]:
    if c not in byed:
        continue
    label, etype = CODEMAP.get(c, (f"その他({c})", "standard"))
    vols = sorted(byed[c], key=lambda x: x.get("number") or 0)
    # 版内 番号dedup(同番号は1つ=ISBN/書影ありを優先)
    bynum = {}
    for v in vols:
        n = v.get("number")
        if n not in bynum or (v.get("cover_url") and not bynum[n].get("cover_url")):
            bynum[n] = v
    vols = [bynum[n] for n in sorted(bynum)]
    if label in seen_label:   # 1950+1951 を1992年版に合流
        seen_label[label]["volumes"].extend(vols)
        seen_label[label]["volumes"].sort(key=lambda x: x.get("number") or 0)
        continue
    ed = {"type": etype, "label": f"日本の歴史 {label}", "publisher": "集英社", "volumes": vols}
    editions.append(ed)
    seen_label[label] = ed

# 巻数多い順(主版を先頭タブに)
editions.sort(key=lambda e: -len(e["volumes"]))

print("=== 集英社 日本の歴史 年代版分離結果 ===")
for e in editions:
    print(f"  [{e['label']}] {e['type']} {len(e['volumes'])}巻: {[v.get('number') for v in e['volumes']]}")

# nihonnorekishi を canonical に再構成 (preview)
base = yaml.safe_load(open(f"{ROOT}/data/manga.v2/nihonnorekishi.yml", encoding="utf-8"))
base["editions"] = editions
base["original_authors"] = [{"name": "児玉幸多", "role": "writer"}]   # 監修(集英社版 日本の歴史 監修)
base["authors"] = [{"name": "児玉幸多", "role": "writer"}]
base["source"] = "edu-manga-preview"
# backup
os.makedirs(f"{ROOT}/.cache/nihonshi-bak", exist_ok=True)
for sl in SRC:
    pp = f"{ROOT}/.preview-data/manga/{sl}.yml"
    if os.path.exists(pp):
        import shutil
        shutil.copy(pp, f"{ROOT}/.cache/nihonshi-bak/{sl}.yml.bak")
yaml.safe_dump(base, open(f"{ROOT}/.preview-data/manga/nihonnorekishi.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
# 重複ページ 2007-2 を preview から除去(統合済)
dup = f"{ROOT}/.preview-data/manga/nippon-no-rekishi-2007-2.yml"
if os.path.exists(dup):
    os.remove(dup)
    print("\n重複ページ nippon-no-rekishi-2007-2 を preview から除去(nihonnorekishiに統合)")
print(f"\npreview再構成完了: nihonnorekishi = {len(editions)}年代版タブ")
