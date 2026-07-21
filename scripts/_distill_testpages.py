"""蒸留試走: 型1/2/3 在scope を テストページ化(.preview-data形式)。種2 read-only。
型1=既存種2作の版を(type×pub)で組み新巻挿入(版表示テスト) / 型2/3=新規ページ。
うる星ルール: (type×冊数)一致を刷タブに畳む(_regroup-versions相当)。書影=楽天CDN。
usage: python _distill_testpages.py [--sample N | --all]  出力先=.cache/distill-testpages/"""
import csv, sqlite3, re, unicodedata, collections, os, sys, json, yaml, urllib.request, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
OUTDIR = f"{ROOT}/.cache/distill-testpages"
os.makedirs(OUTDIR, exist_ok=True)
SAMPLE = None
if "--sample" in sys.argv: SAMPLE = int(sys.argv[sys.argv.index("--sample")+1])

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", str(s)); return re.sub(r"[\s・･,，\.\-—–:：;；!！?？'\"()（）\[\]【】/／]", "", s).strip().lower()
def base_title(t):
    t = str(t or ""); t = re.sub(r"\s*=\s*[A-Za-z].*$", "", t); t = re.sub(r"\s*[\.．]?\s*\d+\s*$", "", t); return re.split(r"[:：]", t)[0].strip()
def volnum(t):
    m = re.search(r"[\.．]?\s*(\d+)\s*$", str(t or "")); return int(m.group(1)) if m else 1
def pref(i):
    i = re.sub(r"\D", "", str(i or ""))
    if len(i) < 13 or not i.startswith("9784"): return i[:7] or "?"
    r = i[4:]; ln = 2 if r[0] in "01" else 3 if r[0] in "23456" else 4 if "70" <= r[:2] <= "84" else 5 if "85" <= r[:2] <= "89" else 6 if "900" <= r[:3] <= "949" else 7
    return i[:4+ln]
TYPE_LABEL = {"standard":"通常版","bunkobon":"文庫版","wideban":"ワイド版","aizoban":"愛蔵版","kanzenban":"完全版","shinsoban":"新装版"}

con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8","replace")
# base題→sid
title2sid = collections.defaultdict(list)
for sid, t in con.execute("SELECT id,title FROM series WHERE title IS NOT NULL"): title2sid[norm(base_title(t))].append(sid)

def cover(isbn):
    for suf in (".jpg", "_1_2.jpg"):
        u = f"https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{isbn[-4:]}/{isbn}{suf}?_ex=200x200"
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=8)
            if "image" in r.headers.get("Content-Type","") and len(r.read()) > 2000: return u
        except: pass
        time.sleep(0.03)
    return None

def build_editions_seed2(sid, new_vols):
    """種2 sid の巻を (type×pub) でグループ→edition化, new_vols(NDL新刊)を該当版へ挿入, (type,冊数)で刷タブ畳み"""
    rows = list(con.execute("""SELECT e.type,e.id,e.imprint,v.number,v.isbn13,v.release_date
        FROM editions e JOIN volumes v ON v.edition_id=e.id WHERE e.series_id=? AND v.isbn13 IS NOT NULL""", (sid,)))
    g = collections.defaultdict(list)
    for ty, eid, imp, n, isbn, rd in rows: g[(ty or "standard", pref(isbn))].append({"number":n,"isbn13":re.sub(r"\D","",isbn),"release_date":rd,"imprint":imp})
    eds = []
    for (ty, p), vs in g.items():
        by_n = {}
        for v in sorted(vs, key=lambda x: str(x["release_date"] or "9999")):
            if v["number"] not in by_n: by_n[v["number"]] = v
        eds.append({"type": ty, "imprint": vs[0]["imprint"], "pub": p, "volumes": sorted(by_n.values(), key=lambda x: x["number"] or 0)})
    # 新刊挿入: 最多巻の standard 版(=本編)へ
    if new_vols and eds:
        main = max((e for e in eds if e["type"] == "standard"), key=lambda e: len(e["volumes"]), default=eds[0])
        exist = {v["number"] for v in main["volumes"]}
        for nv in new_vols:
            if nv["number"] not in exist: main["volumes"].append(nv); main["volumes"].sort(key=lambda x: x["number"] or 0); nv["_new"]=True
    return eds

def regroup(eds):
    """(type,冊数)一致→刷タブ(versions)に畳む(うる星)"""
    grp = collections.defaultdict(list)
    for e in eds: grp[(e["type"], len(e["volumes"]))].append(e)
    out = []
    for (ty, cnt), gg in grp.items():
        gg.sort(key=lambda e: min((v["release_date"] or "9999") for v in e["volumes"]) if e["volumes"] else "9999")
        base = gg[0]
        ed = {"type": ty, "label": f"{TYPE_LABEL.get(ty,'版')}（全{cnt}巻）" if len(gg) > 1 else (base.get("imprint") or TYPE_LABEL.get(ty,"版")),
              "volumes": [{"number":v["number"],"isbn13":v["isbn13"],"release_date":v["release_date"],"cover_url":None} for v in base["volumes"]]}
        if len(gg) > 1:
            ed["versions"] = [{"label": e.get("imprint") or e.get("pub") or f"版{i+1}", "volumes":[{"number":v["number"],"isbn13":v["isbn13"],"release_date":v["release_date"]} for v in e["volumes"]]} for i,e in enumerate(gg)]
        out.append(ed)
    return out

rows = [r for r in csv.DictReader(open(f"{OUTDIR}/../madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in"]
# 既存作(sid)別に型1新刊を集約
by_sid = collections.defaultdict(list); newpages = []
for r in rows:
    bt = norm(base_title(r["title"])); sids = title2sid.get(bt, [])
    nv = {"number": volnum(r["title"]), "isbn13": r["isbn"], "release_date": r["month"].replace("2026-","2026-")}
    if r["type"] == "型1_新刊巻" and sids: by_sid[sids[0]].append((nv, r))
    else: newpages.append(r)
work_items = list(by_sid.items())
if SAMPLE:
    # 多版の型1を優先サンプル
    work_items = sorted(work_items, key=lambda x: -len(set(pref(v[0]["isbn13"]) for v in x[1])))[:SAMPLE]
    newpages = newpages[:SAMPLE]
print(f"型1既存作: {len(by_sid)}作 / 新規ページ(型1未マッチ+型2/3): {len(newpages)}件", flush=True)
n = 0
for sid, items in work_items:
    s = con.execute("SELECT title,title_kana FROM series WHERE id=?", (sid,)).fetchone()
    new_vols = [it[0] for it in items]
    for nv in new_vols: nv["cover_url"] = cover(nv["isbn13"])
    eds = regroup(build_editions_seed2(sid, new_vols))
    slug = "test-" + (norm(s[0])[:30] or f"sid{sid}")
    doc = {"slug": slug, "title": s[0], "title_kana": s[1] or "", "_distill_type": "型1_新刊巻",
           "_new_volumes": [v["isbn13"] for v in new_vols], "editions": eds}
    yaml.safe_dump(doc, open(f"{OUTDIR}/{slug}.yml","w",encoding="utf-8"), allow_unicode=True, sort_keys=False)
    n += 1
    if n % 50 == 0: print(f"  型1 {n}作", flush=True)
print(f"型1 {n}作 生成。新規ページは次段(型2/3)で。出力={OUTDIR}", flush=True)
