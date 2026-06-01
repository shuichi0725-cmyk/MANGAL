"""全DB promote の規模を read-only で見積もる(ライブ/promote 不変)。

slug-final.tsv(全ページ universe)に promote の実DROP定数を適用し、
公開ページ数・各DROP内訳・enrich被覆(synopsis/作品QID/AniList)・
副題区別が要る衝突数を数字化。 = 「全件にしたらどうなるか」の preview。
"""
import sys, json, csv, sqlite3, importlib.util
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path("C:/Users/shuic/code/mangal")
csv.field_size_limit(10**7)

# promote の DROP 定数を実体から import(定義のdrift防止)
spec = importlib.util.spec_from_file_location("promote", ROOT / "scripts/_promote-bulk-v2.py")
pm = importlib.util.module_from_spec(spec)
sys.argv = ["x"]  # --dry-run等を誤検出させない
spec.loader.exec_module(pm)
PRE = pm.DROP_TITLE_PREFIX_PATTERNS
CON = pm.DROP_TITLE_CONTAINS_PATTERNS
SUBP = pm.DROP_SUBTITLE_PATTERNS

# === promote の auto-merge(17,688群)を key→page-canonical に展開 ===
key2page = {}
merges = json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]
for g in merges:
    mk = g.get("merge_keys") or []
    if not mk: continue
    canon = mk[0]  # 群の代表(安定なら何でも可)
    for k in mk:
        key2page[k] = canon
print(f"auto-merge 群: {len(merges):,}  / 統合される series_key: {len(key2page):,}")

# === slug-final 全行を ★auto-merge canonical でページ集約 ===
pages = defaultdict(lambda: {"members": [], "title": None, "vols": 0, "slug": None})
n_rows = 0
with (ROOT / ".cache/slug-final.tsv").open(encoding="utf-8") as f:
    r = csv.DictReader(f, delimiter="\t")
    for row in r:
        n_rows += 1
        k = row["key"]
        pid = key2page.get(k, row["rep"])  # merge群があればそれ、 無ければ slug-final rep
        p = pages[pid]
        p["members"].append(k)
        try: v = int(row["vols"] or 0)
        except: v = 0
        if p["title"] is None or v > p["vols"]:
            p["title"] = row["title"]; p["vols"] = max(p["vols"], v); p["slug"] = row["final_slug"]
print(f"★全ページ(auto-merge適用後)数: {len(pages):,}  / slug-final 行(種3)= {n_rows:,}")

# === 種2 lookup ===
con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
con.text_factory = lambda b: b.decode("utf-8", "replace")
s_title, s_sub, s_adult = {}, {}, {}
for k, t, sub, ad in con.execute("SELECT series_key, title, subtitle, adult_score FROM series"):
    s_title[k] = t; s_sub[k] = sub or ""; s_adult[k] = ad or 0
con.close()

# === maps ===
mag = set()
import yaml
for e in (yaml.safe_load((ROOT / "data/seeds/magazines-drop.yml").read_text(encoding="utf-8")) or {}).get("magazines", []):
    if e.get("series_key"): mag.add(e["series_key"])
enrich = json.load((ROOT / ".cache/anilist-enrich-map.json").open(encoding="utf-8"))
key2aid = {k: str(v["anilist_id"]) for k, v in enrich.items() if isinstance(v, dict) and v.get("anilist_id")}
syn = set(json.load((ROOT / ".cache/synopsis-ja-map.json").open(encoding="utf-8")).keys())
wq = {k for k, v in json.load((ROOT / ".cache/work-qid-map.json").open(encoding="utf-8")).items() if v}

# === 分類 ===
stat = Counter()
title_groups = defaultdict(int)  # base title -> 公開ページ数(衝突検出)
cov = Counter()
for fs, p in pages.items():
    title = p["title"] or ""
    members = p["members"]
    # DROP 判定(promote と同順)
    if any(title.startswith(x) for x in PRE): stat["drop_prefix"] += 1; continue
    if any(x in title for x in CON): stat["drop_contains"] += 1; continue
    if any(m in mag for m in members): stat["drop_magazine"] += 1; continue
    if any(x in s_sub.get(m, "") for m in members for x in SUBP): stat["drop_subtitle"] += 1; continue
    adult = max((s_adult.get(m, 0) for m in members), default=0)
    is_adult = adult >= 5
    stat["published"] += 1
    if is_adult: stat["pub_adult_flag"] += 1
    # 被覆
    aids = [key2aid[m] for m in members if m in key2aid]
    if aids:
        cov["anilist"] += 1
        if any(a in syn for a in aids): cov["synopsis"] += 1
        if any(a in wq for a in aids): cov["work_qid"] += 1
    title_groups[title] += 1

# 衝突 = 同一表示title で 公開ページが2つ以上(副題区別が要る = task2 対象)
collision_titles = {t: n for t, n in title_groups.items() if n >= 2}
collision_pages = sum(n for n in collision_titles.values())

pub = stat["published"]
print("\n=== DROP 内訳 ===")
print(f"  非漫画(prefix=アニメ/劇場版等): {stat['drop_prefix']:,}")
print(f"  関連書(contains=ガイド/設定資料等): {stat['drop_contains']:,}")
print(f"  雑誌(cm105準拠): {stat['drop_magazine']:,}")
print(f"  抜粋本(subtitle): {stat['drop_subtitle']:,}")
print(f"\n=== ★公開ページ数: {pub:,} ===")
print(f"  うち成人フラグ(adult_score>=5・geo出し分け): {stat['pub_adult_flag']:,}")
print("\n=== enrich 被覆(公開ページ中)===")
print(f"  AniList紐付け: {cov['anilist']:,} ({cov['anilist']*100//pub}%)")
print(f"  synopsis和訳: {cov['synopsis']:,} ({cov['synopsis']*100//pub}%)")
print(f"  作品Wikidata QID: {cov['work_qid']:,} ({cov['work_qid']*100//pub}%)")
print("\n=== 衝突(task2=副題/著者で表示区別が要るページ)===")
print(f"  同名で公開ページ2+の題: {len(collision_titles):,} 題  / 該当ページ {collision_pages:,}")
top = sorted(collision_titles.items(), key=lambda x: -x[1])[:10]
for t, n in top:
    print(f"    「{t[:24]}」 {n}ページ")
