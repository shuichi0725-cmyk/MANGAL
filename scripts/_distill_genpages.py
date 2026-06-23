"""蒸留テストページ生成(バッチ): 台帳の統合先に従い、型1=既存本番ページに新巻挿入、型2/3=新規ページ。
書影+caption(synopsis)付与。うる星regroup(同type同冊数→刷タブ)。出力=.preview-data(テスト・差替可)。種2/本番不変(本番はread-only copy)。"""
import csv, json, os, re, unicodedata, yaml, glob, collections, html
ROOT = "C:/Users/shuic/code/MANGAL"
PREV = f"{ROOT}/.preview-data/manga"

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", html.unescape(str(s)))
    return re.sub(r"[\s・･,，\.\-—–:：;；!！?？'\"()（）\[\]【】/／=]", "", s).strip().lower()
def volnum(t):
    m = re.search(r"[\.．]\s*(\d+)\s*$", str(t or "")) or re.search(r"Volume\s+(\d+)", str(t or ""), re.I) or re.search(r"\s+第?(\d+)巻?\s*$", str(t or ""))
    return int(m.group(1)) if m else 1
def pref(i): i = re.sub(r"\D","",str(i or "")); return i[:7] if len(i) >= 7 else (i or "?")
def romaji_slug(t):  # 簡易: ascii化できない→test-<isbn>fallback、英字部だけ抽出
    a = re.sub(r"[^a-zA-Z0-9]+", "-", re.sub(r"[^\x00-\x7f]", "", str(t))).strip("-").lower()
    return a[:40] if len(a) >= 3 else ""

# 索引: 本番ページ title→slug
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
ntitle2slug = {}
for it in idx:
    nt = norm(it["title"])
    if nt and nt not in ntitle2slug: ntitle2slug[nt] = it["slug"]
# enrich: isbn→{cover,caption,affiliate}
enr = {r["isbn"]: r for r in (json.loads(l) for l in open(f"{ROOT}/.cache/distill-enrich.jsonl", encoding="utf-8"))}
ledger = list(csv.DictReader(open(f"{ROOT}/data/seeds/distill-ledger-2026.tsv", encoding="utf-8"), delimiter="\t"))
gap = {r["isbn13"]: r for r in csv.DictReader(open(f"{ROOT}/data/seeds/ndl-2026-gap.tsv", encoding="utf-8"), delimiter="\t")}

def regroup(eds):
    grp = collections.defaultdict(list)
    for e in eds: grp[(e["type"], len(e["volumes"]))].append(e)
    out = []
    for (ty, cnt), gg in grp.items():
        gg.sort(key=lambda e: min((str(v.get("release_date") or "9999") for v in e["volumes"]), default="9999"))
        base = gg[0]
        if len(gg) > 1:
            base["label"] = f"{base.get('label','版')}（全{cnt}巻）"
            base["versions"] = [{"label": e.get("label") or e.get("imprint") or f"版{i+1}", "volumes": e["volumes"]} for i, e in enumerate(gg)]
        out.append(base)
    return out

batch_isbns = set(enr.keys())
n1 = n23 = skip = 0
# ★型1を作品(slug)ごとに集約(複数新刊を1ページに)
work_nv = collections.defaultdict(list)  # slug -> [nv...]
for r in ledger:
    isbn = r["isbn"]
    if isbn not in batch_isbns or r["type"] != "型1_統合": continue
    e = enr.get(isbn, {}); gr = gap.get(isbn, {})
    vn = volnum(gr.get("title", html.unescape(r["title"])))
    nv = {"number": vn, "isbn13": isbn, "release_date": r["month"], "cover_url": e.get("cover") or None, "_distill_new": True}
    m = re.search(r"sid\d+:(.+?)\(", r["integrate_to"]); itt = m.group(1) if m else ""
    slug = ntitle2slug.get(norm(itt))
    if slug: work_nv[slug].append(nv)
    else: skip += 1
for slug, newvols in work_nv.items():
    src = f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(src): skip += len(newvols); continue
    d = yaml.safe_load(open(src, encoding="utf-8"))  # 本番read-only
    eds = d.get("editions", [])
    for nv in newvols:  # 各新刊を出版社一致 or 最多巻 editionへ
        tgt = next((ed for ed in eds if any(pref(v.get("isbn13")) == pref(nv["isbn13"]) for v in ed.get("volumes", []))), None)
        if not tgt: tgt = max(eds, key=lambda x: len(x.get("volumes", [])), default=None)
        if tgt and nv["number"] not in {v.get("number") for v in tgt["volumes"]}:
            tgt["volumes"].append(nv); tgt["volumes"].sort(key=lambda x: x.get("number") or 0)
    d["editions"] = regroup(eds)
    d["_distill"] = f"型1新刊統合: {len(newvols)}巻 {[v['isbn13'] for v in newvols]}"
    out_slug = "z-distill-" + slug
    d["slug"] = out_slug
    yaml.safe_dump(d, open(f"{PREV}/{out_slug}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    n1 += 1
for r in ledger:  # 型2/3 新規
    isbn = r["isbn"]
    if isbn not in batch_isbns or r["type"] == "型1_統合": continue
    e = enr.get(isbn, {}); gr = gap.get(isbn, {})
    title = html.unescape(r["title"]); vn = volnum(gr.get("title", title))
    nv = {"number": vn, "isbn13": isbn, "release_date": r["month"], "cover_url": e.get("cover") or None}
    syn = (e.get("caption") or "")[:140]
    if True:
        cre = gr.get("creators", ""); a0 = re.sub(r",.*$", "", cre.split("/")[0]).strip() if cre else ""
        slug = "z-distill-new-" + (romaji_slug(title) or isbn)
        doc = {"slug": slug, "title": re.sub(r"\s*=.*$", "", re.sub(r"[\.．]\s*\d+\s*$", "", title)).strip(),
               "title_kana": "", "authors": [{"name": a0, "role": "writer_artist"}] if a0 else [],
               "publisher": r["publisher"], "synopsis": syn, "_distill": f"型2/3新規: {isbn}",
               "editions": [{"type": "standard", "label": "通常版", "volumes": [nv]}]}
        yaml.safe_dump(doc, open(f"{PREV}/{slug}.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
        n23 += 1
print(f"生成: 型1統合 {n1} / 型2-3新規 {n23} / skip(本番ページ不明) {skip}")
print(f"出力 .preview-data (prefix z-distill-)")
