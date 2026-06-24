"""テストページ生成(完全版): 2026新刊を完成ページ化。NDL kana→正式slug / NDL出版社 /
楽天caption→synopsis / AI genre / ★status・demographic(loadData必須) / ★型1は既存本番ページ統合(全巻表示)。
種2/本番不変。usage: python _distill_preview.py"""
import csv, json, os, re, glob, unicodedata, yaml, collections
import pykakasi
ROOT = "C:/Users/shuic/code/MANGAL"
PREV = f"{ROOT}/.preview-data/manga"
kks = pykakasi.kakasi()

def slugify(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")
def kana_slug(kana):
    if not kana: return ""
    return slugify("".join(x["hepburn"] for x in kks.convert(kana)))
def base_title(t):
    t = re.sub(r"\s*=\s*[A-Za-z].*$", "", str(t or ""))
    return re.sub(r"[\.．]\s*\d+\s*$", "", t).strip()
def volnum(t):
    m = re.search(r"[\.．]\s*(\d+)\s*$", str(t or "")) or re.search(r"Vol(?:ume)?\.?\s*(\d+)", str(t or ""), re.I)
    return int(m.group(1)) if m else 1
def norm_date(raw):
    """NDL '2026.4'/'2026'→schema形式 'YYYY-MM'/'YYYY'(release_date regex適合)。"""
    if not raw: return None
    s = str(raw).strip()
    m = re.match(r"(\d{4})[.\-/年]\s*(\d{1,2})", s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})", s)
    return m.group(1) if m else None
def norm(s): return re.sub(r"[\s・･:：]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def demographic_of(imprint, pub):
    b = (imprint or "") + (pub or "")
    if re.search(r"少年|ジャンプ|サンデー|マガジン|チャンピオン|ガンガン", b) and "少女" not in b: return "shounen"
    if re.search(r"少女|りぼん|なかよし|花とゆめ|ちゃお|マーガレット", b): return "shoujo"
    if re.search(r"青年|ヤング|ビッグ|モーニング|スピリッツ|アフタヌーン|ゲッサン", b): return "seinen"
    if re.search(r"女性|レディ|ハーレクイン|フラワー|プチ|ハーモニィ|デザート|Kiss", b): return "josei"
    return "other"
KONBINI = re.compile(r"My First BIG|コンビニ|廉価")

enr = {json.loads(l)["isbn"]: json.loads(l) for l in open(f"{ROOT}/data/seeds/distill-enrich-2026.jsonl", encoding="utf-8")}
disc = {r["isbn13"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/ndl-discovery-2026.tsv", encoding="utf-8"), delimiter="\t")}
ledger = {r["isbn"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/distill-ledger-2026.tsv", encoding="utf-8"), delimiter="\t")}
aigenre = json.load(open(f"{ROOT}/data/seeds/distill-genre-ai-2026.json", encoding="utf-8"))
manifest = [r for r in csv.DictReader(open(f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in"]
# 本番 title(norm)→slug(型1の既存ページ統合用)
prod = {}
for it in json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8")):
    nt = norm(it["title"])
    if nt and nt not in prod: prod[nt] = it["slug"]
# ★出版社: NDL社名(norm)→publisherキー(publishers.yml)
PUBMAP = {}
for k, v in yaml.safe_load(open(f"{ROOT}/data/publishers.yml", encoding="utf-8")).items():
    PUBMAP[norm(v.get("name", ""))] = k
    for a in (v.get("aliases") or []): PUBMAP[norm(a)] = k
def pub_key(name):
    nm = norm(name)
    if nm in PUBMAP: return PUBMAP[nm]
    for pn, k in PUBMAP.items():  # 部分一致(NDL社名に支店/版表記が付く場合)
        if pn and (pn in nm or nm in pn) and len(pn) >= 3: return k
    return None

GK = [("isekai", r"異世界|転生"), ("romance", r"恋|愛|令嬢"), ("fantasy", r"魔法|魔王|勇者|冒険"), ("action", r"バトル|戦|復讐"),
      ("comedy", r"ギャグ|コメディ|日常"), ("horror", r"ホラー|怪|恐怖|呪")]
def genres_fallback(blob): return [k for k, p in GK if re.search(p, blob)][:3] or ["drama"]

# 作品単位グループ(同 kana_slug = 1ページ)
works = collections.defaultdict(list)
for r in manifest:
    ib = r["isbn"]; kana = disc.get(ib, {}).get("kana", "")
    works[kana_slug(kana) or f"shinkan-{ib}"].append(ib)

for f in glob.glob(f"{PREV}/*.yml"): os.remove(f)
n = skip_k = t1_merged = 0
for wslug, isbns in works.items():
    isbns.sort(key=lambda i: volnum(disc.get(i, {}).get("title", "")))
    first = disc.get(isbns[0], {}); lt0 = ledger.get(isbns[0], {})
    series = first.get("series", "")
    if KONBINI.search(series): skip_k += 1; continue
    title = base_title(first.get("title", "")); kana = first.get("kana", "")
    is_t1 = lt0.get("type", "").startswith("型1")
    # 新刊巻(discovery分)
    new_vols = []
    for ib in isbns:
        di = disc.get(ib, {}); ei = enr.get(ib, {})
        cov = ei.get("cover") if (ei.get("cover") and "noimage" not in (ei.get("cover") or "")) else None
        new_vols.append({"number": volnum(di.get("title", "")), "isbn13": ib, "release_date": norm_date(di.get("date", "")), "cover_url": cov, "_new": True})
    # ★型1: 既存本番ページの全巻を取り込む(1巻問題解消)
    slug = wslug; eds = None; existing = 0; t1_pub = None; t1_pubs = []
    if is_t1:
        m = re.search(r"sid\d+:(.+?)\(", lt0.get("integrate_to", "")); itt = m.group(1) if m else ""
        psl = prod.get(norm(itt)) or prod.get(norm(title))
        pf = f"{ROOT}/data/manga.v2/{psl}.yml" if psl else None
        if pf and os.path.exists(pf):
            pd = yaml.safe_load(open(pf, encoding="utf-8"))
            slug = psl; eds = pd.get("editions", [])
            existing = sum(len(e.get("volumes", [])) for e in eds)
            main = max(eds, key=lambda e: len(e.get("volumes", [])), default=None)
            if main:
                have = {v.get("number") for v in main["volumes"]}
                for nv in new_vols:
                    if nv["number"] not in have: main["volumes"].append(nv)
                main["volumes"].sort(key=lambda v: v.get("number") or 0)
            t1_merged += 1
            t1_pub = pd.get("publisher"); t1_pubs = pd.get("publishers", []) or []
            if pd.get("title"): title = pd["title"]
            if pd.get("title_kana"): kana = pd["title_kana"]
    if eds is None:
        eds = [{"type": "standard", "label": "通常版", "volumes": new_vols}]
    cap = next((enr.get(i, {}).get("caption", "") for i in isbns if enr.get(i, {}).get("caption")), "")
    cre = first.get("creators", "")
    authors = [{"name": re.sub(r"\s*(著|原作|作画|漫画|∥.*|/.*)$", "", a).strip(), "role": "writer_artist"}
               for a in cre.split("/")[:3] if a.strip()] or [{"name": "(unknown)", "role": "writer_artist"}]
    yr = int(re.sub(r"\D", "", str(first.get("date", "2026"))[:4]) or 2026)
    genres = aigenre.get(wslug) or genres_fallback(title + " " + cap)
    # ★出版社: 型1=既存ページの社尊重 / 型3=NDL社→キー
    if is_t1 and t1_pub:
        p_key, p_list = t1_pub, t1_pubs
    else:
        pk = pub_key(first.get("publisher", "")); p_key = pk or "(unknown)"; p_list = [pk] if pk else []
    for e in (eds or []):  # edition単位の社も埋める(型3の新規edition)
        if not e.get("publisher") and p_key != "(unknown)": e["publisher"] = p_key
    doc = {"slug": slug, "title": title, "title_kana": kana, "title_romaji": kana_slug(kana).replace("-", " ") or slug,
           "year_started": yr, "year_ended": None, "status": "ongoing",
           "authors": authors, "publisher": p_key, "publishers": p_list, "_publisher_raw": first.get("publisher", ""), "_imprint": series,
           "demographic": demographic_of(series, first.get("publisher", "")),
           "genres": [g for g in genres if g][:4] or ["drama"], "genres_provisional": True,
           "first_volume_date": norm_date(first.get("date", "")), "synopsis": cap[:140],
           "_distill": f"2026新刊 {'型1新刊巻(既存'+str(existing)+'巻+新刊)' if is_t1 and existing else '型3新規'} ISBN{isbns[0]}",
           "editions": eds}
    yaml.safe_dump(doc, open(f"{PREV}/{slug}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    n += 1
print(f"完全版テストページ: {n}作品 (型1既存統合 {t1_merged} / コンビニ非掲載 {skip_k})")
print("status/demographic追加(loadData通過)・型1=既存全巻+新刊・genre=AI/synopsis=楽天")
