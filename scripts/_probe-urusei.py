"""「うる星やつら」 の 種2/種3 認識状況。
- series row 全部
- 種3 紐付き状況
- edition / volume 取込状況
- cluster 統合状況
"""
import sqlite3
from pathlib import Path
import yaml

con = sqlite3.connect(".cache/db-v2.sqlite")
con.row_factory = sqlite3.Row

print("=== series (= title に 「うる星やつら」 含む) ===")
srows = con.execute(
    "SELECT id, series_key, qid, title, subtitle, year_started, year_ended, "
    "       publisher_key, magazine_key, genres, adult_score "
    "FROM series WHERE title LIKE '%うる星やつら%' ORDER BY id"
).fetchall()
for r in srows:
    print(f"  sid={r['id']:>6}, qid={r['qid']!r:<14}, title={r['title']!r}, sub={r['subtitle']!r}")
    print(f"          publ={r['publisher_key']!r}, mag={r['magazine_key']!r}, "
          f"adult={r['adult_score']}, year={r['year_started']}-{r['year_ended']}")

if not srows:
    print("  (none)")
    raise SystemExit

ids = [r["id"] for r in srows]
ph = ",".join("?" * len(ids))

# 種3 紐付き check
with open("data/seeds/series-supplement-v2.yml", encoding="utf-8") as f:
    seed3 = yaml.safe_load(f)
seed3_keys = {e["key"] for e in seed3["series"]}
seed3_qids = set()
for e in seed3["series"]:
    if e["key"].startswith("qid:"):
        seed3_qids.add(e["key"].split("|", 1)[0][4:])

print()
print("=== 種3 紐付き状況 ===")
for r in srows:
    by_key = r["series_key"] in seed3_keys
    by_qid = r["qid"] and r["qid"] in seed3_qids
    linked = "[OK]" if (by_key or by_qid) else "[NG]"
    print(f"  sid={r['id']}: {linked}  by_key={by_key}, by_qid={by_qid}")
    if by_key:
        # 種3 の entry detail
        e = next((s for s in seed3["series"] if s["key"] == r["series_key"]), None)
        if e:
            print(f"          seed3 entry: alt_en={e.get('alternative_titles', {}).get('en')}, "
                  f"genres={e.get('genres')}, status={e.get('status')}")

print()
print("=== editions + volume 取込 状況 ===")
erows = con.execute(
    f"SELECT id, series_id, type, label, imprint FROM editions WHERE series_id IN ({ph}) ORDER BY series_id, id",
    ids,
).fetchall()
for e in erows:
    vols = con.execute(
        "SELECT number, volume_label, release_date, isbn13 "
        "FROM volumes WHERE edition_id=? ORDER BY CAST(number AS INTEGER), id",
        (e["id"],),
    ).fetchall()
    print(f"  sid={e['series_id']:>6}, eid={e['id']}, type={e['type']:<10}, imprint={e['imprint']!r}")
    if vols:
        nums = [v["number"] for v in vols]
        labels = [v["volume_label"] for v in vols if v["volume_label"]]
        print(f"          {len(vols)} vol, numbers={nums[:15]}{'...' if len(nums)>15 else ''}")
        if labels:
            print(f"          labels (= 一部): {labels[:5]}")

# cluster_key 計算 (= 全 sid どの cluster になるか)
print()
print("=== cluster_key 計算 (= audit 視点) ===")
import re, unicodedata
def _clean(s):
    if not s: return ""
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "Z"): continue
        if ch in "ー―~〜": continue
        out.append(ch.lower())
    return "".join(out)
def norm_title(t, sub):
    return _clean(t) + "|" + _clean(sub)

# merge yml 読み込み
alias_to_main = {}
import yaml
try:
    with open("data/seeds/series-merge.yml", encoding="utf-8") as f:
        for entry in (yaml.safe_load(f) or []):
            for a in entry.get("aliases", []) or []:
                alias_to_main[a] = entry["main"]
except FileNotFoundError:
    pass

# 同 norm の 全 series (qid mapping)
all_series = con.execute("SELECT id, qid, title, subtitle FROM series").fetchall()
title_to_qid = {}
main_to_qid = {}
for r in all_series:
    if r["qid"]:
        t = alias_to_main.get(r["title"], r["title"])
        key = norm_title(t, r["subtitle"])
        title_to_qid.setdefault(key, r["qid"])
    if r["qid"] and r["title"] in alias_to_main:
        main_to_qid.setdefault(alias_to_main[r["title"]], r["qid"])

cluster_groups = {}
for r in srows:
    effective_title = alias_to_main.get(r["title"], r["title"])
    if r["qid"]:
        ckey = f"qid:{r['qid']}"
    elif effective_title in main_to_qid:
        ckey = f"qid:{main_to_qid[effective_title]}"
    else:
        norm = norm_title(effective_title, r["subtitle"])
        if norm in title_to_qid:
            ckey = f"qid:{title_to_qid[norm]}"
        else:
            ckey = f"title:{norm}"
    cluster_groups.setdefault(ckey, []).append(r["id"])

for ckey, sids in cluster_groups.items():
    print(f"  cluster_key={ckey}")
    print(f"    sids={sids}")
