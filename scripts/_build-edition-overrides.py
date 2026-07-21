"""preview で editions を変更した教育系ページを edition-overrides.json に固める(本番promote durability)。
preview と 本番 data/manga.v2 で editions(巻ISBN集合)が異なるページを抽出し、 preview の editions(+著者) を override seed 化。
promote が最後にこの seed でページの editions/著者を置換 → 再promoteで年代版分離・補完が再現。"""
import glob, os, yaml, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)

def isbn_set(d):
    s = set()
    for e in d.get("editions", []) or []:
        for v in e.get("volumes", []) or []:
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            if ib:
                s.add(ib)
    return s

overrides = {}
for p in glob.glob(f"{ROOT}/.preview-data/manga/*.yml"):
    sl = os.path.splitext(os.path.basename(p))[0]
    prod = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(prod):
        continue
    try:
        dp = yaml.safe_load(open(p, encoding="utf-8"))
        dprod = yaml.safe_load(open(prod, encoding="utf-8"))
    except Exception:
        continue
    if not dp or not dprod:
        continue
    if dp.get("source") != "edu-manga-preview":
        continue
    # editions(巻ISBN集合 or edition構成)が違う = 編集された
    pv_eds = [(e.get("type"), e.get("label"), tuple(sorted(re.sub(r"\D", "", str(v.get("isbn13") or "")) for v in e.get("volumes", [])))) for e in dp.get("editions", [])]
    pr_eds = [(e.get("type"), e.get("label"), tuple(sorted(re.sub(r"\D", "", str(v.get("isbn13") or "")) for v in e.get("volumes", [])))) for e in dprod.get("editions", [])]
    if pv_eds == pr_eds:
        continue
    # override: editions全体 + 著者(変更時)
    overrides[sl] = {"editions": dp["editions"]}
    if dp.get("authors") != dprod.get("authors"):
        overrides[sl]["authors"] = dp.get("authors", [])
    if dp.get("original_authors") != dprod.get("original_authors"):
        overrides[sl]["original_authors"] = dp.get("original_authors", [])
    if dp.get("credits") != dprod.get("credits"):
        overrides[sl]["credits"] = dp.get("credits", [])

json.dump(overrides, open(f"{ROOT}/data/seeds/edition-overrides.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"edition-overrides.json: {len(overrides)}ページ")
for sl, ov in overrides.items():
    neds = len(ov["editions"])
    nvol = sum(len(e.get("volumes", [])) for e in ov["editions"])
    extra = [k for k in ("authors", "original_authors", "credits") if k in ov]
    print(f"  {sl:34} {neds}版 {nvol}巻 {('著者上書' + str(extra)) if extra else ''}")
