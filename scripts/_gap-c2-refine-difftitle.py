"""gap c-2: DIFF_TITLE 263群を フリガナ(読み)+前方一致+著者 で精緻に振り分け(★merge無し・調査)。

DIFF_TITLE = 別surface題で同slug衝突・著者共有。 内訳を3つに分ける:
  ① SUBTITLE_APPEND = 一方が他方の前方一致(あすなろ白書 ⊂ あすなろ白書 学生編)
       → 別ページ・副題で区別(merge でない)。
  ② ORTHO_MERGE    = 同じ読み × 同じ著者集合(惡の華⇄悪の華、安倍窪⇄安部窪、Akuma no mama⇄あくまのまま)
       → 同一作の旧字/誤字/表記違い = ★真の merge 候補(要外部確証)。
  ③ HOMOPHONE_SUFFIX = 同じ読み × 別著者(緋い花/紅い花=別作者の同音異作)
       → 別作品 → 接尾辞(c-1 と同じ)。
  ④ MIXED/OTHER = 上に当てはまらない(>2 ページで構造混在等) → 手動確認。

※調査のみ。 出力 .cache/gap-c2-difftitle.tsv + 集計。
"""
import csv
import pickle
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / ".cache" / "slug-final.tsv"
CLS = ROOT / ".cache" / "gap-c2-classify.tsv"
PKL = ROOT / ".cache" / "seed3-promote.pkl"
MANGAKA = ROOT / "data" / "seed" / "mangaka.csv"
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / ".cache" / "gap-c2-difftitle.tsv"


def nstrip(t):
    t = unicodedata.normalize("NFKC", t or "")
    return re.sub(r"[\s　・,，.。!！?？\-―ー~〜=【】\[\]()（）「」『』:：;；/／♥❤☆★]", "", t).lower()


def nkana(k):
    k = unicodedata.normalize("NFKC", k or "")
    return re.sub(r"[\s　・]", "", k)


def build_resolver():
    by = {}
    with MANGAKA.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["name"]:
                by.setdefault(r["name"], r["qid"])
            for a in (r.get("alt_names") or "").split("|"):
                if a:
                    by.setdefault(a, r["qid"])
    return by


def author_set(rep, by):
    s = {p[4:] for p in rep.split("|") if p.startswith("qid:")}
    names = [p[5:] for p in rep.split("|") if p.startswith("name:")]
    if len(names) >= 2:
        s.add(by.get(names[0], names[0]))
    return frozenset(s)


def load_foreign():
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    agg = defaultdict(list)
    for sk, isbn in con.execute(
        "SELECT s.series_key,v.isbn13 FROM series s JOIN editions e ON e.series_id=s.id "
        "JOIN volumes v ON v.edition_id=e.id WHERE v.isbn13 IS NOT NULL"
    ):
        agg[sk].append(str(isbn).replace("-", ""))
    con.close()
    return {sk: (not any(i.startswith("9784") for i in ibs)) for sk, ibs in agg.items()}


def is_prefix_chain(norms):
    """最短が他全ての前方一致(かつ真に短い)なら True = 副題append構造。"""
    s = sorted(set(norms), key=len)
    base = s[0]
    return len(s) >= 2 and all(o != base and o.startswith(base) for o in s[1:])


def main():
    by = build_resolver()
    foreign = load_foreign()
    diff_bases = {r["base"] for r in csv.DictReader(CLS.open(encoding="utf-8"), delimiter="\t")
                  if r["disposition"].startswith("DIFF_TITLE")}

    d = pickle.load(PKL.open("rb"))
    key2kana = {e["key"]: (e.get("title_kana") or "") for e in d.values()}

    groups = defaultdict(list)
    seen = set()
    with FINAL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] in seen:
                continue
            seen.add(r["rep"])
            if r["base_slug"] in diff_bases:
                groups[r["base_slug"]].append(r)

    rows = []
    cat = defaultdict(int)
    for base, pages in groups.items():
        real = [p for p in pages if not (foreign.get(p["rep"]) is True) and int(p["vols"] or 0) > 0]
        if len(real) < 2:
            disp = "RESOLVED_BY_DROP"
        else:
            norms = [nstrip(p["title"]) for p in real]
            kanas = {nkana(key2kana.get(p["rep"], "")) for p in real}
            kanas.discard("")
            auths = [author_set(p["rep"], by) for p in real]
            same_auth = len(set(auths)) == 1
            if is_prefix_chain(norms):
                disp = "SUBTITLE_APPEND"
            elif len(kanas) == 1:
                disp = "ORTHO_MERGE" if same_auth else "HOMOPHONE_SUFFIX"
            else:
                disp = "MIXED_OTHER"
        cat[disp] += 1
        det = " || ".join(
            f"{p['title'][:14]}〔{nkana(key2kana.get(p['rep'],''))[:10]}〕(v{p['vols']},{p['year'] or '—'})"
            for p in pages
        )
        rows.append((disp, base, det))

    with OUT.open("w", encoding="utf-8") as f:
        f.write("disposition\tbase\tpages\n")
        for x in sorted(rows):
            f.write("\t".join(x) + "\n")

    print(f"=== gap c-2 DIFF_TITLE {len(groups):,}群 精緻振り分け(merge無し) → {OUT.name} ===")
    for k, v in sorted(cat.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
