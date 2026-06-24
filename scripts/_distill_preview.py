"""テストページ生成(正式fill版): 2026新刊を NDL kana→正式slug / NDL出版社 / コンビニ判定(imprint) /
楽天caption→synopsis で完成ページ化。作品単位グループ(同slug=複数巻=1ページ)。穴だらけ仮表示を廃止。
genre は caption keyword 暫定(genres_provisional=true。 正式AIは後続)。種2/本番不変。"""
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
    rj = "".join(x["hepburn"] for x in kks.convert(kana))
    return slugify(rj)
def base_title(t):
    t = re.sub(r"\s*=\s*[A-Za-z].*$", "", str(t or ""))
    return re.sub(r"[\.．]\s*\d+\s*$", "", t).strip()
def volnum(t):
    m = re.search(r"[\.．]\s*(\d+)\s*$", str(t or "")) or re.search(r"Vol(?:ume)?\.?\s*(\d+)", str(t or ""), re.I)
    return int(m.group(1)) if m else 1

# コンビニ廉価/特殊レーベル(imprintで判定)
KONBINI = re.compile(r"My First BIG|コンビニ|廉価|SPコミックス.*廉価|あおばコミックス|principle|ぐる")

enr = {json.loads(l)["isbn"]: json.loads(l) for l in open(f"{ROOT}/data/seeds/distill-enrich-2026.jsonl", encoding="utf-8")}
disc = {r["isbn13"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/ndl-discovery-2026.tsv", encoding="utf-8"), delimiter="\t")}
ledger = {r["isbn"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/distill-ledger-2026.tsv", encoding="utf-8"), delimiter="\t")}
manifest = [r for r in csv.DictReader(open(f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in"]

# genre: caption keyword(暫定)
GK = [("isekai", r"異世界|転生|転移"), ("romance", r"恋|愛|初恋|婚約|令嬢|溺愛|結婚|花嫁"), ("fantasy", r"魔法|魔王|勇者|ドラゴン|精霊|ファンタジ|冒険"),
      ("action", r"バトル|戦い|討伐|戦争|復讐|戦士"), ("gourmet", r"グルメ|料理|ごはん|めし|食べ"), ("horror", r"ホラー|怪|恐怖|呪|ゾンビ|心霊"),
      ("mystery", r"ミステリ|探偵|殺人|事件|謎|刑事"), ("school", r"学園|高校|生徒|青春|部活"), ("comedy", r"ギャグ|コメディ|笑|日常"),
      ("sports", r"野球|サッカー|スポーツ|球|テニス"), ("supernatural", r"妖怪|幽霊|超能力|あやかし"), ("ecchi", r"お色気|えっち|発情")]
def genres_from(blob):
    g = [k for k, p in GK if re.search(p, blob)][:3]
    return g or ["drama"]

# 作品単位グループ(同 kana_slug = 1ページ・複数巻)
works = collections.defaultdict(list)
for r in manifest:
    ib = r["isbn"]; d = disc.get(ib, {})
    kana = d.get("kana", "")
    slug = kana_slug(kana) or f"shinkan-{ib}"
    works[slug].append(ib)

# 既存テストページ全消去
for f in glob.glob(f"{PREV}/*.yml"): os.remove(f)

n = skip_konbini = 0
for slug, isbns in works.items():
    isbns.sort(key=lambda i: volnum(disc.get(i, {}).get("title", "")))
    first = disc.get(isbns[0], {}); e0 = enr.get(isbns[0], {})
    series = first.get("series", "")
    if KONBINI.search(series):  # コンビニ廉価=非掲載(確証まで)
        skip_konbini += 1; continue
    title = base_title(first.get("title", ""))
    kana = first.get("kana", "")
    cap = next((enr.get(i, {}).get("caption", "") for i in isbns if enr.get(i, {}).get("caption")), "")
    cre = first.get("creators", "")
    authors = [{"name": re.sub(r"\s*(著|原作|作画|漫画|/.*|∥.*)$", "", a).strip(), "role": "writer_artist"}
               for a in cre.split("/")[:3] if a.strip()] or [{"name": "(unknown)", "role": "writer_artist"}]
    yr = int(re.sub(r"\D", "", str(first.get("date", "2026"))[:4]) or 2026)
    vols = []
    for ib in isbns:
        di = disc.get(ib, {}); ei = enr.get(ib, {})
        cov = ei.get("cover") if (ei.get("cover") and "noimage" not in (ei.get("cover") or "")) else None
        vols.append({"number": volnum(di.get("title", "")), "isbn13": ib, "release_date": di.get("date", ""), "cover_url": cov})
    doc = {"slug": slug, "title": title, "title_kana": kana,
           "title_romaji": kana_slug(kana).replace("-", " ") or title, "year_started": yr,
           "subtitle": None, "authors": authors, "publisher": "(unknown)",  # 出版社キー化は後続(生社名=first['publisher'])
           "_publisher_raw": first.get("publisher", ""), "_imprint": series,
           "genres": genres_from(title + " " + cap), "genres_provisional": True,
           "first_volume_date": first.get("date", ""), "synopsis": cap[:140],
           "_distill": f"2026新刊 ISBN{isbns[0]}",
           "editions": [{"type": "standard", "label": "通常版", "volumes": vols}]}
    yaml.safe_dump(doc, open(f"{PREV}/{slug}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    n += 1
print(f"正式fillテストページ: {n}作品 (コンビニ非掲載 {skip_konbini}) / 元巻 {len(manifest)}")
print(f"slug=NDL kana由来(正式フォルダ名)・出版社/imprint=NDL・synopsis=楽天caption・genre=暫定")
