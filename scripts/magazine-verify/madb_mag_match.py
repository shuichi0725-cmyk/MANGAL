"""MADB「初出」× 本番の連載誌 の突合(読むだけ)。
頁ごとに MADB で一番古い巻の初出の先頭誌を取り、 雑誌マスタのキーに引いて、 今の連載誌と比べる。"""
import json, re, sys, unicodedata, yaml, csv
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
D = ".cache/magazine-lists"

def norm(s):
    return re.sub(r"[\s・･.．!！'’「」『』\-‐－〜~]", "", unicodedata.normalize("NFKC", s or "").lower())

MAG = yaml.safe_load(open("data/magazines.yml", encoding="utf-8"))
name2key = {norm(v["name"]): k for k, v in MAG.items()}
ALIAS = {"週刊少年シャンプ": "weekly-shonen-jump", "ジャンプスクエア": "jump-sq", "ジャンプsq": "jump-sq",
         "ララ": "lala", "週刊少年ジャンプ増刊最強ジャンプ": "saikyo-jump", "月刊少年ガンガン増刊ガンガンパワード": "gangan-powered",
         "週刊ビッグコミックスピリッツ": "big-comic-spirits", "モーニング": "morning", "週刊モーニング": "morning",
         "月刊アフタヌーン": "afternoon", "週刊ヤングサンデー": "weekly-young-sunday", "ヤングサンデー": "weekly-young-sunday",
         "週刊ヤングマガジン": "weekly-young-magazine", "ヤングマガジン": "weekly-young-magazine",
         "ヤングジャンプ": "weekly-young-jump", "少年ジャンプ": "weekly-shonen-jump", "少年マガジン": "weekly-shonen-magazine",
         "少年サンデー": "weekly-shonen-sunday", "少年チャンピオン": "champion", "週刊少年チャンピオン": "champion",
         "少年ジャンプ+": "shonen-jump-plus", "少年ジャンププラス": "shonen-jump-plus", "ジャンププラス": "shonen-jump-plus",
         "月刊gファンタジー": "gfantasy", "gファンタジー": "gfantasy", "コミック電撃大王": "dengeki-daioh", "電撃大王": "dengeki-daioh",
         "月刊コミックブレイド": "comic-blade", "コミックブレイド": "comic-blade", "月刊ガンガンwing": "gangan-wing", "ガンガンwing": "gangan-wing",
         "月刊ガンガンjoker": "gangan-joker", "ガンガンjoker": "gangan-joker", "月刊ビッグガンガン": "big-gangan", "ビッグガンガン": "big-gangan",
         "月刊サンデージェネックス": "monthly-sunday-gx", "サンデージェネックス": "monthly-sunday-gx", "月刊サンデーgx": "monthly-sunday-gx",
         "月刊コンプエース": "comp-ace", "コンプエース": "comp-ace", "月刊comicrex": "comic-rex", "comicrex": "comic-rex", "コミックレックス": "comic-rex",
         "月刊少年エース": "shonen-ace", "少年エース": "shonen-ace", "ヤングエース": "young-ace", "be・love": "be-love", "belove": "be-love",
         "ヤングキングアワーズ": "young-king-ours", "漫画アクション": "manga-action", "月刊アクション": "monthly-action",
         "週刊漫画ゴラク": "weekly-manga-goraku", "漫画ゴラク": "weekly-manga-goraku", "まんがタイムきらら": "manga-time-kirara",
         "ガンガンonline": "gangan-online", "マガジンポケット": "manga-pocket", "少年マガジンエッジ": "shonen-magazine-edge"}
for a, k in ALIAS.items():
    name2key.setdefault(norm(a), k)

def first_mag(text):
    t = text.split("初出", 1)[1] if "初出" in text else text
    m = re.search(r"[「『]([^」』]+)[」』]", t)
    if m:
        return m.group(1).strip()
    m = re.match(r"\s*[:：]?\s*([^0-9０-９、,，/（(]+)", t)   # 括弧なし「初出：月刊コミック乱2015年5月号」
    return (m.group(1).strip() if m else "")

def all_mags(text):
    t = text.split("初出", 1)[1] if "初出" in text else text
    return [x.strip() for x in re.findall(r"[「『]([^」』]+)[」』]", t)]

pidx = json.load(open(".cache/isbn-page-index.json", encoding="utf-8"))
li = json.load(open("data/manga-list-index.json", encoding="utf-8"))
F = {k: i for i, k in enumerate(li["f"])}
page = {r[F["slug"]]: {"title": r[F["title"]], "mag": r[F["magazine"]] or "", "pub": r[F["publisher"]] or "", "year": r[F["year_started"]] or 0} for r in li["d"]}

rows = [json.loads(l) for l in open(f"{D}/madb-shoshutsu.jsonl", encoding="utf-8")]
by_slug = defaultdict(list)
miss_isbn = 0
for r in rows:
    if r["kind"] != "book" or not r["isbn"]:
        continue
    isbn = re.sub(r"[^0-9X]", "", r["isbn"])
    slugs = pidx.get(isbn)
    if not slugs:
        miss_isbn += 1
        continue
    for s in slugs:
        by_slug[s].append(r)
print("初出つき巻(ISBNあり)", sum(1 for r in rows if r["kind"] == "book" and r["isbn"]), "/ 本番頁に当たらない", miss_isbn, "/ 当たった頁", len(by_slug))

def volkey(r):
    m = re.search(r"\d+", unicodedata.normalize("NFKC", r["vol"] or ""))
    return (r["date"] or "9999", int(m.group()) if m else 9999)

fixed = {json.loads(l)["slug"] for l in open("data/seeds/magazine-fix-changelog.jsonl", encoding="utf-8")}
unres = {}
for row in csv.DictReader(open("docs/production-diagnostics/magazine-unresolved-2026-11-04.tsv", encoding="utf-8"), delimiter="\t"):
    unres[row["slug"]] = row["区分"]

res = []
for s, rs in by_slug.items():
    if s not in page:
        continue
    rs.sort(key=volkey)
    first = rs[0]
    fm = first_mag(first["text"])
    fk = name2key.get(norm(fm), "")
    # 全巻を通した先頭誌の集計(最初の巻だけだと番外編巻に引かれることがある)
    heads = Counter(name2key.get(norm(first_mag(r["text"])), "?" + first_mag(r["text"])) for r in rs)
    cur = page[s]["mag"]
    if not fk:
        cls = "雑誌マスタに無い誌"
    elif not cur:
        cls = "空欄→埋められる"
    elif cur == fk:
        cls = "一致"
    else:
        cls = "食い違い"
    grp = "是正した736頁" if s in fixed else ("未解決表" if s in unres else "その他")
    res.append({"slug": s, "title": page[s]["title"], "cur": cur, "madb_key": fk, "madb_name": fm, "grp": grp, "cls": cls,
                "vols": len(rs), "heads": dict(heads), "first_vol": first["vol"], "first": f'{first["title"]} {first["vol"]} {first["date"]}: {first["text"][:100]}'})

c = Counter((x["grp"], x["cls"]) for x in res)
for g in ("是正した736頁", "未解決表", "その他"):
    print(g, {k[1]: v for k, v in c.items() if k[0] == g})
print("マスタに無い誌の上位:", Counter(x["madb_name"] for x in res if x["cls"] == "雑誌マスタに無い誌").most_common(40))
json.dump(res, open(f"{D}/madb-vs-page.json", "w", encoding="utf-8"), ensure_ascii=False)
