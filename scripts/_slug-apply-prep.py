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

# ★成年ゲート(2026-06-13 追加): adult_score>=3 の series は本番ページにしない。
#   発端 = あまとりあ社41頁(貧乳日記)露出 → 全数調査で2,233頁が無ガード公開と判明
#   (従来パイプラインは成年フィルタがどこにも配線されていなかった=5月の本番化から)。
#   例外 = data/seeds/adult-overrides.yml の force_adult:False(種aで全年齢確認済み)。
#   将来 = 成年3分けレビューUI([[adult_triage_review_pending]])で人が確定後に解放。
import sqlite3
import yaml as _yaml
_con = sqlite3.connect(ROOT / ".cache" / "db-v2.sqlite")
_con.text_factory = lambda b: b.decode("utf-8", "replace")
adult_keys = {r[0] for r in _con.execute("SELECT series_key FROM series WHERE adult_score>=3")}
_con.close()
_ovr_doc = _yaml.safe_load((ROOT / "data" / "seeds" / "adult-overrides.yml").read_text(encoding="utf-8")) or {}
_ovr = {
    o["series_key"]
    for o in (_ovr_doc.get("overrides") or [])
    if isinstance(o, dict) and o.get("force_adult") is False and o.get("series_key")
}
adult_keys -= _ovr

# ★rep(=ページ代表key)単位で 1ページ=1行。 全key出しにすると merge群の同slug共有を
#   apply-build が cap衝突と誤認して "-2" 偽ページを量産する(2026-06-11 修正)。
key2slug = {}
drop_keys = set()
split_reps = set()
adult_held = set()
for r in integ:
    rep = r["rep"]
    s = r["proposed_slug"]
    if rep in adult_keys or r["key"] in adult_keys:
        adult_held.add(rep)
        key2slug.pop(rep, None)
        continue
    if s == "(DROP)":
        drop_keys.add(rep)
    elif s.startswith("(SPLIT"):
        split_reps.add(rep)
    elif s and rep not in key2slug:
        key2slug[rep] = s
drop_keys |= adult_held

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
print(f"key2slug:{len(key2slug):,} / 残merge群:{len(merges)}(Stage A-3適用済なら0) / drop:{len(drop_keys)}(うち★成年hold:{len(adult_held):,}) / split(recluster)rep:{len(split_reps)} / recluster ISBN:{len(recl)}")
