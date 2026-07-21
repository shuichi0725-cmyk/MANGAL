"""教育マンガの1版内ISBN出版社prefix混在を分離。 多数派prefix=正規出版社を残し、
少数派prefix巻=別出版社(=別作)を除去候補に(volume-exclude)。 ISBN出版者記号=事実境界。 [[publisher_model_edition_level]]
dry-run(既定): 除去候補をdocs出力。 --apply: volume-exclude.yml追記 + preview反映。"""
import json, yaml, re, os, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
APPLY = "--apply" in sys.argv

def reg(isbn):
    if not isbn.startswith("9784") or len(isbn) != 13:
        return None
    b = isbn[4:12]; n2 = int(b[:2])
    return b[:2] if n2 <= 19 else b[:3] if n2 <= 69 else b[:4] if n2 <= 84 else b[:5] if n2 <= 89 else b[:6] if n2 <= 94 else b[:7]

# 教育slug (index: kodomo + 教育題)
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
fi = {k: i for i, k in enumerate(idx["f"])}
EDU = re.compile(r"世界の歴史|日本の歴史|まんが日本|歴史人物|伝記|偉人|学習まんが|学習漫画|科学漫画|科学まんが|サバイバル|図鑑|大百科|ことわざ|四字熟語|百人一首|慣用句|なぜ\?|ひみつ|実験|学研まんが|発見!|大研究|の秘密|入門")
edu_slugs = [r[fi["slug"]] for r in idx["d"]
             if r[fi["demographic"]] == "kodomo" and (EDU.search(r[fi["title"]] or "") or "historical" in (r[fi["genres"]] or []))]

excludes = []   # (slug, isbn, main_prefix, minority_prefix, title)
mixed = 0
for sl in edu_slugs:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    try:
        d = yaml.safe_load(open(p, encoding="utf-8"))
    except Exception:
        continue
    for e in d.get("editions", []):
        byreg = {}
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            r = reg(ib)
            if r:
                byreg.setdefault(r, []).append((v.get("number"), ib))
        if len(byreg) <= 1:
            continue
        top = max(byreg, key=lambda k: len(byreg[k])); topn = len(byreg[top])
        tot = sum(len(x) for x in byreg.values())
        if topn / tot < 0.6:
            continue  # 過半でない=版違いの可能性 → 慎重にskip(報告のみ)
        mixed += 1
        for r, vols in byreg.items():
            if r == top:
                continue
            for num, ib in vols:
                excludes.append((sl, ib, top, r, d.get("title", "")[:24], num))

print(f"教育作 {len(edu_slugs)} / 1版内prefix混在(主過半) {mixed} / 除去候補ISBN {len(excludes)}")
import collections
bytitle = collections.Counter(x[4] for x in excludes)
print("=== 除去候補(主prefix≠の少数派=別出版社) ===")
for sl, ib, top, r, t, num in excludes[:30]:
    print(f"  {t:26} vol{num} 主{top}≠{r} (isbn{ib})")
json.dump(excludes, open(f"{ROOT}/.cache/edu-exclude.json", "w", encoding="utf-8"), ensure_ascii=False)

if APPLY:
    # volume-exclude.yml 追記
    add = []
    for sl, ib, top, r, t, num in excludes:
        add.append(f'  - slug: {sl}\n    isbn13: "{ib}"\n    reason: 教育系の別出版社混入(主prefix{top}≠{r}=別出版社=別シリーズ)。ISBN出版者記号で分離。vol{num}\n    at: "2026-06-29"\n')
    with open(f"{ROOT}/data/seeds/volume-exclude.yml", "a", encoding="utf-8") as f:
        f.write("".join(add))
    # preview反映(除去)
    ex_by_slug = collections.defaultdict(set)
    for sl, ib, top, r, t, num in excludes:
        ex_by_slug[sl].add(ib)
    pv = 0
    for sl, ibs in ex_by_slug.items():
        pp = f"{ROOT}/.preview-data/manga/{sl}.yml"
        if not os.path.exists(pp):
            continue
        d = yaml.safe_load(open(pp, encoding="utf-8"))
        for e in d.get("editions", []):
            e["volumes"] = [v for v in e.get("volumes", []) if re.sub(r"\D", "", str(v.get("isbn13") or "")) not in ibs]
        yaml.safe_dump(d, open(pp, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
        pv += 1
    print(f"APPLIED: volume-exclude +{len(excludes)} / preview更新 {pv}作")
