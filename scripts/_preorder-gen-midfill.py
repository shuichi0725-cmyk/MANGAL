#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約④: 途中巻でページ無し(取りこぼし作品)のpreviewドラフト生成 (= 2026-07-06)

classified.json の ex_mid を、楽天キャッシュ(isbn-title-map)で全巻回収してから生成する
(=「単巻先行登録禁止・全巻回収が先」protocolの機械適用)。
ゲート: kana/author/ym必須 / 回収巻が1..Nの80%以上連続 / slug衝突なし。
キャッシュで揃わない作品は保留(worklist)=liveハーベストは別途。
"""
import json, os, re, sys, datetime, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()

# gen-previewのローマ字化/strip関数を流用(import)
import importlib.util
spec = importlib.util.spec_from_file_location("genprev", os.path.join(ROOT, "scripts", "_preorder-gen-preview.py"))
# ファイル実行を避けるため必要関数だけ再定義(軽量コピー)
exec(open(os.path.join(ROOT, "scripts", "_preorder-gen-preview.py"), encoding="utf-8").read().split("# 既存slug集合")[0])

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", t).lower()

VOLP = re.compile(r"[（(]\s*(\d{1,3})\s*[)）]\s*$|\s+(\d{1,3})\s*$|第\s*(\d{1,3})\s*巻\s*$")
def split_vol(title):
    t = unicodedata.normalize("NFKC", str(title or "")).strip()
    m = VOLP.search(t)
    if m:
        n = next((g for g in m.groups() if g), None)
        return norm(VOLP.sub("", t)), (int(n) if n else None)
    return norm(t), None

tm = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
iidx = json.load(open(f"{ROOT}/.cache/isbn-page-index.json", encoding="utf-8"))
# 題base→ [(vol, isbn)] の逆引き(キャッシュ全巻回収)
by_base = {}
for ib, t in tm.items():
    if not ib.startswith("9784"):
        continue
    b, v = split_vol(t)
    if v is not None:
        by_base.setdefault(b, {}).setdefault(v, ib)

existing = set()
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
si = idx["f"].index("slug")
for r in idx["d"]:
    existing.add(r[si])
import glob as _g
for p in _g.glob(f"{ROOT}/.preview-data/manga/*.yml"):
    existing.add(os.path.basename(p)[:-4])

DEMO = {"少年": "shonen", "少女": "shojo", "青年": "seinen", "レディース": "josei"}
def author_names(s):
    return [x.strip() for x in re.split(r"[/,、;；]", str(s or "")) if x.strip()]

cls = json.load(open(f"{ROOT}/.cache/preorders/classified.json", encoding="utf-8"))
made, holds, pend = [], [], []
VOLSTRIP = re.compile(r"[\s　]*(?:[（(]\s*\d{1,3}\s*[)）]|第\s*\d{1,3}\s*巻|\d{1,3})\s*$")
def strip_vol_disp(t):
    t2 = VOLSTRIP.sub("", str(t or "").strip())
    return t2 if t2 else str(t or "").strip()

for r in cls["ex_mid"]:
    title = strip_vol_disp(r.get("title"))
    kana = strip_vol_disp(r.get("titleKana"))
    ym = r.get("ym")
    auths = author_names(r.get("author"))
    akanas = author_names(r.get("authorKana"))
    if not (title and kana and ym and auths):
        holds.append((r.get("isbn"), title, "必須欠け")); continue
    base = r.get("_base") or split_vol(r.get("title"))[0]
    vols_map = dict(by_base.get(base) or {})
    vols_map[r["_vol"]] = r["isbn"]  # 予約巻自身
    # 既に他頁で描画中のISBNが混ざる=別作品の可能性→その巻は除外
    vols_map = {v: ib for v, ib in vols_map.items() if ib not in iidx or ib == r["isbn"]}
    ns = sorted(vols_map)
    if not ns or ns[0] != 1 or len(ns) < 0.8 * ns[-1] or len(ns) < 2:
        holds.append((r.get("isbn"), title, f"全巻回収不成立 vols={ns[:6]}{'..' if len(ns)>6 else ''}")); continue
    romaji = kana2romaji(kana)
    if not romaji or len(romaji) < 2:
        holds.append((r.get("isbn"), title, "slug生成不可")); continue
    slug = romaji[:70]
    if slug in existing:
        slug = f"{slug}-{ym[:4]}"
        if slug in existing:
            holds.append((r.get("isbn"), title, f"slug衝突 {slug}")); continue
    existing.add(slug)
    volumes = []
    for v in ns:
        ib = vols_map[v]
        rd = (ym + (f"-{r['day']:02d}" if r.get("day") else "")) if ib == r["isbn"] else None
        cov = r.get("cover") if ib == r["isbn"] else f"https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{ib[9:12]}/{ib}.jpg?_ex=200x200"
        volumes.append({"number": v, "asin": None, "isbn13": ib, "cover_url": cov, "release_date": rd})
    authors = []
    for i2, name in enumerate(auths):
        a = {"name": name}
        if i2 < len(akanas) and akanas[i2]:
            a["kana"] = akanas[i2]
        authors.append(a)
    doc = {"slug": slug, "title": title,
           "title_kana": kana.replace(" ", "").replace("　", ""),
           "title_romaji": romaji.replace("-", " "),
           "authors": authors, "year_started": int(ym[:4]), "status": "ongoing",
           "demographic": DEMO.get(r.get("subgenre")), "genres": [],
           "editions": [{"type": "standard", "label": "通常版", "publisher": r.get("publisher"),
                          "imprint": r.get("seriesName") or "", "volumes": volumes}],
           "_preorder_draft": {"class": "ex_mid", "added_at": TODAY, "source": "rakuten-preorder",
                               "note": f"取りこぼし作品(予約巻v{r['_vol']}発見→キャッシュ全巻回収{len(ns)}冊)。過去巻の日付/確証は本番化前にNDL等で要補完"}}
    yaml.dump(doc, open(f"{ROOT}/.preview-data/manga/{slug}.yml", "w", encoding="utf-8"),
              allow_unicode=True, sort_keys=False, width=200)
    made.append(slug)
    pend.append(json.dumps({"isbn": r["isbn"], "slug": slug, "title": title, "title_kana": kana,
                            "authors": auths, "author_kanas": akanas, "added_at": TODAY,
                            "status": "pending"}, ensure_ascii=False))

with open(f"{ROOT}/data/seeds/rakuten-kana-pending.jsonl", "a", encoding="utf-8") as f:
    for ln in pend:
        f.write(ln + "\n")
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "a", encoding="utf-8") as f:
    for isbn, title, why in holds:
        f.write(f"ex_mid_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t{why}\n")
json.dump(made, open(f"{ROOT}/.cache/preorders/preview-made-exmid.json", "w"))
print(f"ex_mid: 生成{len(made)} / 保留{len(holds)}(キャッシュで全巻揃わず等)")
