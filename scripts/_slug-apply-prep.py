"""slug適用の入力を full key で構築(冪等・再実行可)。 .cache/apply/ に出力。 ★seed追記はしない(検証用)。

★2026-06-11 改修: 単一ソース = data/seeds/slug-final-integrated.tsv(_integrate-slugs.py 生成)。
旧実装は slug-final + option1 + c2suffix を直読みしており、 NDL fix 層(slug-fix-candidates)が
適用入力に流れない構造だった → 統合TSV(全layer済・一意性検証済)に一本化。

  - key2slug.tsv      : series_key → 最終slug(全key。 merge群は同slugで自然に1ページ)
  - merges-c2.json    : c2 merge_all 群(★Stage A-3 で series-merge-auto 適用済 → 通常 0 件)
  - drop-keys.txt     : (DROP) 行の rep(c3外国orphan/partial outlier/NDL junk/c1外国版)
  - recluster-vol.tsv : ISBN → recluster slug(slug-volume-final)
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

integ = dr("data/seeds/slug-final-integrated.tsv")

key2slug = {}
drop_keys = set()
split_reps = set()
for r in integ:
    s = r["proposed_slug"]
    if s == "(DROP)":
        drop_keys.add(r["rep"])
    elif s.startswith("(SPLIT"):
        split_reps.add(r["rep"])
    elif s:
        key2slug[r["key"]] = s

# c2 merge_all: Stage A-3 で series-merge-auto 適用済のため、 未吸収(reps≥2が現存)のみ拾う(通常0)
reps_alive = {r["rep"] for r in integ}
merges = []
for r in dr("data/seeds/slug-c2-merge-candidates.tsv"):
    if r["verdict"] != "merge_all":
        continue
    reps = [x for x in (r.get("reps") or "").split("\x1f") if x and x in reps_alive]
    if len(reps) >= 2:
        merges.append({"main_base": r["base"], "merge_keys": reps, "note": "c2-ndl-merge"})

recl = {r["isbn13"]: r["final_slug"] for r in dr("data/seeds/slug-volume-final.tsv")}

with (A/"key2slug.tsv").open("w",encoding="utf-8") as f:
    f.write("key\tslug\n")
    for k,s in key2slug.items(): f.write(f"{k}\t{s}\n")
json.dump(merges, (A/"merges-c2.json").open("w",encoding="utf-8"), ensure_ascii=False)
(A/"drop-keys.txt").write_text("\n".join(sorted(drop_keys)),encoding="utf-8")
with (A/"recluster-vol.tsv").open("w",encoding="utf-8") as f:
    f.write("isbn13\tslug\n")
    for i,s in recl.items(): f.write(f"{i}\t{s}\n")
print(f"key2slug:{len(key2slug):,} / 残merge群:{len(merges)}(Stage A-3適用済なら0) / drop:{len(drop_keys)} / split(recluster)rep:{len(split_reps)} / recluster ISBN:{len(recl)}")
