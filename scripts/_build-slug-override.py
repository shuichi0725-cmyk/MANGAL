"""gap a/b の確定 slug 候補を 1 つの key→base_slug override に統合する。

入力 (= 全て committed seed / 候補 TSV):
  - data/seeds/slug-katakana-en-candidates.tsv (gap a = カタカナ英綴り。 key 付き)
  - data/seeds/slug-num-fixed-candidates.tsv    (gap b 数字。 key 無し → V2 から再導出)
  - data/seeds/slug-latinmix-candidates.tsv     (gap b latin-mixed。 idx → V2 から key 再導出)

★title-join は使わない (title 非一意で誤統合=致命的)。 gap b は V2(.cache/slug-gen-v2.tsv)
  の source==kana-num 行 (= key 付き) を _slug-num-fix.classify_and_fix で決定的に再分類し、
  latin-mixed は出現順 idx ↔ key で安全に結ぶ。

出力 .cache/slug-override.tsv (key, base_slug, src)。 ※調査/中間生成のみ、 本番不変。
_slug-assemble.py がこれを読んで base_slug に最優先で適用する。
"""
import csv
import importlib.util
import pickle
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / ".cache" / "slug-gen-v2.tsv"
PKL = ROOT / ".cache" / "seed3-promote.pkl"
GAPA = ROOT / "data" / "seeds" / "slug-katakana-en-candidates.tsv"
GAPB_LATIN = ROOT / "data" / "seeds" / "slug-latinmix-candidates.tsv"
OUT = ROOT / ".cache" / "slug-override.tsv"

# gap a = 確信分のみ適用 (keep_hepburn / ai_low は既存ロジックに委ねる = 慎重)
GAPA_APPLY = {"ai_high", "web_confirmed", "web_corrected", "ai_accepted"}


def _load_numfix():
    spec = importlib.util.spec_from_file_location("nf", ROOT / "scripts" / "_slug-num-fix.py")
    nf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nf)
    return nf


def main():
    nf = _load_numfix()
    d = pickle.load(PKL.open("rb"))
    key2seg = {e["key"]: (e.get("title_kana_segmented") or e.get("title_kana") or "") for e in d.values()}
    v2_rows = list(csv.DictReader(V2.open(encoding="utf-8"), delimiter="\t"))

    override = {}  # key -> (slug, src)
    conflicts = 0

    def put(key, slug, src):
        nonlocal conflicts
        slug = (slug or "").strip()
        if not key or not slug:
            return
        if key in override and override[key][0] != slug:
            conflicts += 1
            print(f"  CONFLICT {key[:36]} {override[key]} vs {(slug, src)}")
        override[key] = (slug, src)

    # --- gap a (key 付き、 確信分のみ) ---
    na = 0
    with GAPA.open(encoding="utf-8") as f:
        for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter="\t"):
            if r["status"] in GAPA_APPLY:
                put(r["key"], r["en_slug"], "gapA")
                na += 1

    # --- gap b: V2 kana-num を決定的に再分類して key 再導出 ---
    kana_num = [r for r in v2_rows if r["source"] == "kana-num"]
    lm_keys = []
    nb_num = 0
    for r in kana_num:
        seg = key2seg.get(r["key"], "")
        new, typ, _ = nf.classify_and_fix(r["title"], seg, r["slug"])
        if "latin-mixed" in typ:
            lm_keys.append(r["key"])  # 出現順 = candidate idx
        elif new != r["slug"]:
            put(r["key"], new, "gapB-num")
            nb_num += 1

    # latin-mixed: idx ↔ key (出現順)
    lm_cand = {int(r["idx"]): r["new_slug"] for r in csv.DictReader(GAPB_LATIN.open(encoding="utf-8"), delimiter="\t")}
    nb_lm = 0
    for i, key in enumerate(lm_keys):
        if i in lm_cand:
            put(key, lm_cand[i], "gapB-latin")
            nb_lm += 1

    with OUT.open("w", encoding="utf-8") as f:
        f.write("key\tbase_slug\tsrc\n")
        for k, (s, src) in override.items():
            f.write(f"{k}\t{s}\t{src}\n")

    print(f"override 計 {len(override)}: gapA={na} gapB-num={nb_num} gapB-latin={nb_lm} (conflict={conflicts})")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
