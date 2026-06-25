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
    t = re.sub(r"[\.．]\s*\[?\d+\]?\s*$", "", t)  # ". 8" / ". [8]"
    return re.sub(r"\s*\[\d+\]\s*$", "", t).strip()  # 末尾 "[8]"
def volnum(t):
    m = re.search(r"[\.．]\s*\[?(\d+)\]?\s*$", str(t or "")) or re.search(r"Vol(?:ume)?\.?\s*(\d+)", str(t or ""), re.I) or re.search(r"\[(\d+)\]\s*$", str(t or ""))
    return int(m.group(1)) if m else 1
def vol_of(d):
    """★巻番号は dcndl:volume(discovery volume列)を優先(題parseより信頼)。 '[8]'等のブラケットも数字抽出。"""
    v = re.sub(r"\D", "", str(d.get("volume", "")))
    return int(v) if v else volnum(d.get("title", ""))
def norm_date(raw):
    """NDL '2026.4'/'2026'/'[2026.5]'(推定=ブラケット付)→schema形式 'YYYY-MM'/'YYYY'。"""
    if not raw: return None
    s = re.sub(r"[\[\]()]", "", str(raw)).strip()  # ★ブラケット除去([2026.5]→2026.5)
    m = re.match(r"(\d{4})[.\-/年]\s*(\d{1,2})", s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})", s)
    return m.group(1) if m else None
def year_of(raw):
    """★日付から開始年を堅牢に抽出(ブラケット/推定日付対応)。 '[2026.5]'→2026。"""
    m = re.search(r"(\d{4})", str(raw or ""))
    return int(m.group(1)) if m else 2026
def norm(s): return re.sub(r"[\s・･:：]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def demographic_of(imprint, pub):
    b = (imprint or "") + (pub or "")
    if re.search(r"少年|ジャンプ|サンデー|マガジン|チャンピオン|ガンガン", b) and "少女" not in b: return "shounen"
    if re.search(r"少女|りぼん|なかよし|花とゆめ|ちゃお|マーガレット", b): return "shoujo"
    if re.search(r"青年|ヤング|ビッグ|モーニング|スピリッツ|アフタヌーン|ゲッサン", b): return "seinen"
    if re.search(r"女性|レディ|ハーレクイン|フラワー|プチ|ハーモニィ|デザート|Kiss", b): return "josei"
    return "other"
KONBINI = re.compile(r"My First BIG|コンビニ|廉価")
# ★非漫画/アンソロ誌/雑誌mook(著者なし18件調査で確定): title/series で検出
NONMANGA_TITLE = re.compile(r"アンソロ|アニメコミック|読者投稿|公式ファンブック|フィルムコミック|セレクション")
# ★SJR=集英社ジャンプリミックス(コンビニ廉価) / リミックス/REMIX も同種
NONMANGA_SERIES = re.compile(r"ムック|[Mm][Oo][Oo][Kk]|ぐる漫|読者投稿|MAY'S|SJR|リミックス|[Rr][Ee][Mm][Ii][Xx]")

enr = {json.loads(l)["isbn"]: json.loads(l) for l in open(f"{ROOT}/data/seeds/distill-enrich-2026.jsonl", encoding="utf-8")}
disc = {r["isbn13"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/ndl-discovery-2026.tsv", encoding="utf-8"), delimiter="\t")}
ledger = {r["isbn"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/distill-ledger-2026.tsv", encoding="utf-8"), delimiter="\t")}
aigenre = json.load(open(f"{ROOT}/data/seeds/distill-genre-ai-2026.json", encoding="utf-8"))
manifest = [r for r in csv.DictReader(open(f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in"]
# ★成年除外(distill-adult-2026.tsv=成年publisher/title語で再判定した111冊。 publisher欠落時のscope分類漏れを補正)
adult_isbns = {r["isbn13"] for r in csv.DictReader(open(f"{ROOT}/data/seeds/distill-adult-2026.tsv", encoding="utf-8"), delimiter="\t")}
# ★非商業ドロップ(distill-drop-2026.tsv=学校PTA冊子等の手動ドロップ管理リスト) + 団体著者ヒューリスティック
drop_isbns = {r["isbn13"] for r in csv.DictReader(open(f"{ROOT}/data/seeds/distill-drop-2026.tsv", encoding="utf-8"), delimiter="\t")}
# ★著者補完(distill-author-supplement-2026.tsv=discovery取りこぼし著者をNDL per-ISBNで補完。 isbn→'name:role/...')
import os as _os
AUTHOR_SUP = {}
_asf = f"{ROOT}/data/seeds/distill-author-supplement-2026.tsv"
if _os.path.exists(_asf):
    AUTHOR_SUP = {r["isbn13"]: r["creators_roled"] for r in csv.DictReader(open(_asf, encoding="utf-8"), delimiter="\t")}
# ★真の抜けfill(distill-fill-2026.jsonl=NDL題検索で著者一致取得した earlier volumes。 slug→全巻)
FILL = {}
_ff = f"{ROOT}/data/seeds/distill-fill-2026.jsonl"
if _os.path.exists(_ff):
    for _l in open(_ff, encoding="utf-8"):
        _d = json.loads(_l); FILL[_d["slug"]] = _d
# ★統合override(distill-integrate-override-2026.tsv=題trunc/著者役職で照合漏れた統合ミスを preview_slug→本番slug で繋ぐ。 続編は除外済)
INTEGRATE_OVR = {}
_iof = f"{ROOT}/data/seeds/distill-integrate-override-2026.tsv"
if _os.path.exists(_iof):
    INTEGRATE_OVR = {r["preview_slug"]: r["prod_slug"] for r in csv.DictReader(open(_iof, encoding="utf-8"), delimiter="\t")}
ORG_AUTHOR = re.compile(r"協議会|委員会|PTA|連盟|教育委員|学校長会|振興会|商工会")
# 本番 title(norm)→slug + title_kana(norm)→slug(型1統合の名寄せ。 ★kana照合でローマ字/カナ題不一致を吸収)
prod = {}; prod_kana = {}
for it in json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8")):
    nt = norm(it["title"])
    if nt and nt not in prod: prod[nt] = it["slug"]
    nk = norm(it.get("title_kana", ""))
    if nk and nk not in prod_kana: prod_kana[nk] = it["slug"]
def clean_author(a):
    """NDL '姓, 名, 1936-2021' / '細川 智栄子' → '姓名'(空白・区切り・生没年除去)。"""
    a = re.sub(r"\s*,?\s*\d{4}\s*-\s*\d{0,4}", "", str(a or ""))  # 生没年
    a = re.sub(r"\s*(著|原作|作画|漫画|編|画|劇)\s*$", "", a)  # 末尾役割語
    return re.sub(r"[\s　,、／/∥]", "", a).strip()  # 空白・カンマ・区切り 全除去
def parse_authors(roled):
    """creators_roled 'name:role/...'→ authors/original_authors/credits分離。★∥／で共著者分割。"""
    orig, arts, creds = [], [], []
    for c in (roled or "").split("/"):
        name_part, _, role = c.partition(":")
        for nm in re.split(r"[∥／]", name_part):  # ★共著者(細川智栄子∥芙〜みん)を分割
            name = clean_author(nm)
            if not name: continue
            if role == "原作": orig.append(name)
            elif role in ("漫画", "作画", "画", "著", "劇画", "作", ""): arts.append(name)
            else: creds.append({"name": name, "role": role})  # キャラクターデザイン/原案/構成等
    if orig:  # ★原作あり=作画者はartist / 原作なし=単独writer_artist
        authors = [{"name": n, "role": "artist"} for n in arts] or [{"name": "(unknown)", "role": "artist"}]
        original_authors = [{"name": n, "role": "writer"} for n in orig]
    else:
        authors = [{"name": n, "role": "writer_artist"} for n in arts] or [{"name": "(unknown)", "role": "writer_artist"}]
        original_authors = []
    return authors, original_authors, creds
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
n = skip_k = skip_a = skip_d = skip_sp = t1_merged = 0
for wslug, isbns in works.items():
    isbns.sort(key=lambda i: vol_of(disc.get(i, {})))
    if any(i in adult_isbns for i in isbns): skip_a += 1; continue  # ★成年=preview非掲載(adult stream/geoで別扱い)
    first = disc.get(isbns[0], {}); lt0 = ledger.get(isbns[0], {})
    if any(i in drop_isbns for i in isbns) or ORG_AUTHOR.search(first.get("creators", "")):
        skip_d += 1; continue  # ★非商業(学校PTA冊子/団体著者)=ドロップ
    series = first.get("series", "")
    if KONBINI.search(series): skip_k += 1; continue
    # ★非漫画/アンソロ誌/雑誌mook(著者なし18件調査): title「アンソロ/アニメコミック/読者投稿」or series「ムック/ぐる漫/MAY'S」→drop
    if NONMANGA_TITLE.search(first.get("title", "")) or NONMANGA_SERIES.search(series):
        skip_d += 1; continue
    # ★コンビニ廉価/特装の絶版reprint: leed/扶桑(reprint版元) かつ 楽天に無い(絶版=標準小売外)→非掲載
    if pub_key(first.get("publisher", "")) in ("leed", "fusosha") and not any(enr.get(i, {}).get("rk_title") for i in isbns):
        skip_k += 1; continue
    title = base_title(first.get("title", "")); kana = first.get("kana", "")
    is_t1 = lt0.get("type", "").startswith("型1")
    # 新刊巻(discovery分)
    new_vols = []
    for ib in isbns:
        di = disc.get(ib, {}); ei = enr.get(ib, {})
        cov = ei.get("cover") if (ei.get("cover") and "noimage" not in (ei.get("cover") or "")) else None
        new_vols.append({"number": vol_of(di), "isbn13": ib, "release_date": norm_date(di.get("date", "")), "cover_url": cov, "_new": True})
    # ★型1: 既存本番ページの全巻を取り込む(1巻問題解消)
    slug = wslug; eds = None; existing = 0; t1_pub = None; t1_pubs = []; t1_year = None
    # ★巻番≥2 = 既刊がある継続巻 → 型1でなくても既存ページへ統合を試みる(solo_nonfirst解消)
    max_newvol = max((v["number"] for v in new_vols), default=1)
    if is_t1 or max_newvol >= 2:
        m = re.search(r"sid\d+:(.+?)\(", lt0.get("integrate_to", "")); itt = m.group(1) if m else ""
        psl = INTEGRATE_OVR.get(wslug) or prod.get(norm(itt)) or prod.get(norm(title)) or prod_kana.get(norm(kana))  # ★override+kana照合
        pf = f"{ROOT}/data/manga.v2/{psl}.yml" if psl else None
        if pf and os.path.exists(pf):
            pd = yaml.safe_load(open(pf, encoding="utf-8"))
            slug = psl; eds = pd.get("editions", [])
            existing = sum(len(e.get("volumes", [])) for e in eds)
            main = max(eds, key=lambda e: len(e.get("volumes", [])), default=None)
            if main:
                have = {v.get("number") for v in main["volumes"]}
                added = sum(1 for nv in new_vols if nv["number"] not in have)
                if added == 0:  # ★新巻ゼロ=reprint/重複が本編に誤マッチ(ドカベン文庫型)→非掲載
                    skip_sp += 1; continue
                for nv in new_vols:
                    if nv["number"] not in have: main["volumes"].append(nv)
                main["volumes"].sort(key=lambda v: v.get("number") or 0)
            t1_merged += 1
            t1_pub = pd.get("publisher"); t1_pubs = pd.get("publishers", []) or []
            t1_year = pd.get("year_started")  # ★既存ページの開始年を継承(出版年矛盾の解消)
            if pd.get("title"): title = pd["title"]
            if pd.get("title_kana"): kana = pd["title_kana"]
    if eds is None:
        eds = [{"type": "standard", "label": "通常版", "volumes": new_vols}]
    cap = next((enr.get(i, {}).get("caption", "") for i in isbns if enr.get(i, {}).get("caption")), "")
    cre = first.get("creators", "")
    roled_src = AUTHOR_SUP.get(isbns[0]) or first.get("creators_roled", "") or "/".join(f"{a}:" for a in re.split(r"[/／]", cre))
    authors, original_authors, credits = parse_authors(roled_src)
    yr = t1_year or year_of(first.get("date", "2026"))
    # ★真の抜けfill: earlier volumes(著者一致取得済)を統合(書影=enrich)、開始年を最古巻へ繰り上げ
    fb = FILL.get(slug)
    if fb and fb.get("volumes"):
        main = max(eds, key=lambda e: len(e.get("volumes", [])), default=eds[0])
        have = {v.get("number") for v in main["volumes"]}
        for fv in fb["volumes"]:
            if fv["number"] not in have:
                ei = enr.get(fv["isbn13"], {})
                cov = ei.get("cover") if (ei.get("cover") and "noimage" not in (ei.get("cover") or "")) else None
                main["volumes"].append({"number": fv["number"], "isbn13": fv["isbn13"], "release_date": fv.get("release_date"), "cover_url": cov})
        main["volumes"].sort(key=lambda v: v.get("number") or 0)
        if fb["volumes"][0].get("release_date"): yr = min(yr, year_of(fb["volumes"][0]["release_date"]))
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
           "authors": authors, "original_authors": original_authors, "credits": credits,
           "publisher": p_key, "publishers": p_list, "_publisher_raw": first.get("publisher", ""), "_imprint": series,
           "demographic": demographic_of(series, first.get("publisher", "")),
           "genres": [g for g in genres if g][:4] or ["drama"], "genres_provisional": True,
           "first_volume_date": norm_date(first.get("date", "")), "synopsis": cap[:140],
           "_distill": f"2026新刊 {'型1新刊巻(既存'+str(existing)+'巻+新刊)' if is_t1 and existing else '型3新規'} ISBN{isbns[0]}",
           "editions": eds}
    yaml.safe_dump(doc, open(f"{PREV}/{slug}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    n += 1
print(f"完全版テストページ: {n}作品 (型1既存統合 {t1_merged} / コンビニ非掲載 {skip_k} / 成年非掲載 {skip_a} / 非商業 {skip_d} / reprint誤マッチ {skip_sp})")
print("status/demographic追加(loadData通過)・型1=既存全巻+新刊・genre=AI/synopsis=楽天")
