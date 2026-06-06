"""slug適用の入力を full key で構築(冪等・再実行可)。 .cache/apply/ に出力。 ★seed追記はしない(検証用)。
  - key2slug.tsv      : series_key → 最終slug
  - merges-c2.json    : c2 merge_all 群 → {main_base, merge_keys(既存群flatten union)}
  - drop-keys.txt     : c3 drop + partial outlier の series_key
  - recluster-vol.tsv : ISBN → recluster slug
"""
import sys, csv, json
from collections import defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
A = ROOT / ".cache" / "apply"; A.mkdir(parents=True, exist_ok=True)
SEEDS = ROOT / "data" / "seeds"
def dr(fn):
    return list(csv.DictReader((ROOT / fn).open(encoding="utf-8"), delimiter="\t"))

key2slug = {}
for r in dr(".cache/slug-final.tsv"):
    key2slug[r["rep"]] = r["base_slug"]
for fn in ["data/seeds/slug-collision-option1-candidates.tsv", "data/seeds/slug-c2-suffix-candidates.tsv"]:
    for r in dr(fn):
        if r["new_slug"] and r["new_slug"] != "(DROP)":
            key2slug[r["key"]] = r["new_slug"]

base2reps = defaultdict(list); seen = set()
for r in dr(".cache/slug-final.tsv"):
    if r["rep"] in seen: continue
    seen.add(r["rep"]); base2reps[r["base_slug"]].append(r["rep"])

# 既存merge群: key→全merge_keys
existing = json.load((SEEDS / "series-merge-auto.json").open(encoding="utf-8")).get("merges", [])
key2group = {}
for e in existing:
    mk = e.get("merge_keys") or []
    for k in mk: key2group[k] = mk

c2 = {r["base"]: (r["verdict"], set(filter(None, (r.get("outliers") or "").split("|")))) for r in dr("data/seeds/slug-c2-merge-candidates.tsv")}
merges = []
for base, (v, outl) in c2.items():
    if v != "merge_all": continue
    reps = base2reps.get(base, [])
    if len(reps) < 2: continue
    union = []
    for rep in reps:
        for k in key2group.get(rep, [rep]):
            if k not in union: union.append(k)
    merges.append({"main_base": base, "merge_keys": union, "note": "c2-ndl-merge"})

drop_keys = set()
c3titles = {r["title"] for r in dr("data/seeds/slug-malformed-triage-candidates.tsv") if "drop" in r["disposition"]}
partial_outliers = {base: outl for base, (v, outl) in c2.items() if v == "partial"}
DKW = ["COLOR WALK","RED","アート","画集","アニメブック","フィルムコミック","How to","THE 11TH","THE 12TH","THE 13TH","THE 14TH"]
for r in dr(".cache/slug-final.tsv"):
    if r["title"] in c3titles: drop_keys.add(r["rep"])
    b = r["base_slug"]
    if b in partial_outliers:
        for ol in partial_outliers[b]:
            if ol and ol[:10] in r["title"] and any(k in ol for k in DKW):
                drop_keys.add(r["rep"]); break

recl = {r["isbn13"]: r["final_slug"] for r in dr("data/seeds/slug-volume-final.tsv")}

with (A/"key2slug.tsv").open("w",encoding="utf-8") as f:
    f.write("key\tslug\n")
    for k,s in key2slug.items(): f.write(f"{k}\t{s}\n")
json.dump(merges, (A/"merges-c2.json").open("w",encoding="utf-8"), ensure_ascii=False)
(A/"drop-keys.txt").write_text("\n".join(sorted(drop_keys)),encoding="utf-8")
with (A/"recluster-vol.tsv").open("w",encoding="utf-8") as f:
    f.write("isbn13\tslug\n")
    for i,s in recl.items(): f.write(f"{i}\t{s}\n")
tot=sum(len(m["merge_keys"]) for m in merges)
print(f"key2slug:{len(key2slug):,} / merge群:{len(merges)}(統合keys計{tot}) / drop:{len(drop_keys)} / recluster ISBN:{len(recl)}")
