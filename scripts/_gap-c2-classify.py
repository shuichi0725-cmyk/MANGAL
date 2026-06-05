"""gap c-2: merge漏れ336群を「中身」で安全に機械仕分け(★merge一切なし・調査のみ)。

merge漏れは綺麗な merge 対象ではなく、 外国版/雑誌/v0スタブ/真の同一作断片/版違い/option2
が混入している。 これらを保守的シグナルで分類して規模を可視化する。

各ページを foreign(全ISBN非9784) / v0(0巻) でタグ付けし、 残り「実ページ」を:
  - 同題×同著者集合 → MERGE_CANDIDATE(表記揺れ/年断片=安全な merge 候補)
  - 同題×別著者多数 → ANTHOLOGY?(雑誌drop疑い)
  - 同題×別著者少数 → AUTHOR_SPLIT(表記揺れ merge か option2 か=Web裁定)
  - 版KW(カラー/版/全集) → EDITION(版統合)
  - 別題×著者共有 → DIFF_TITLE(option2/別漫画化/無関係=Web裁定)
出力 .cache/gap-c2-classify.tsv + 集計。
"""
import csv
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / ".cache" / "slug-final.tsv"
TRIAGE = ROOT / ".cache" / "slug-collision-triage.tsv"
MANGAKA = ROOT / "data" / "seed" / "mangaka.csv"
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / ".cache" / "gap-c2-classify.tsv"

EDITION_KW = re.compile(r"カラー|フルカラー|完全版|愛蔵版|新装版|文庫|ワイド|豪華版|総天然色|大全集|復刻")


def norm_title(t):
    t = unicodedata.normalize("NFKC", t or "")
    t = re.sub(r"[\s　・,，.。!！?？\-―ー~〜=【】\[\]()（）「」『』:：;；/／]", "", t)
    return t.lower()


def build_resolver():
    by_name = {}
    with MANGAKA.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            q = r["qid"]
            if r["name"]:
                by_name.setdefault(r["name"], q)
            for alt in (r.get("alt_names") or "").split("|"):
                if alt:
                    by_name.setdefault(alt, q)
    return by_name


def author_set(rep, by_name):
    auth = set()
    for p in rep.split("|"):
        if p.startswith("qid:"):
            auth.add(p[4:])
    names = [p[5:] for p in rep.split("|") if p.startswith("name:")]
    if len(names) >= 2:
        a = names[0]
        auth.add(by_name.get(a, a))
    return auth


def is_latin(s):
    return bool(re.search(r"[A-Za-z]", s)) and not re.search(r"[ぁ-んァ-ヴ一-鿿]", s)


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


def main():
    by_name = build_resolver()
    foreign = load_foreign()
    merge_bases = {r["base"] for r in csv.DictReader(TRIAGE.open(encoding="utf-8"), delimiter="\t")
                   if r["category"] == "merge_miss"}

    # slug-final を rep 重複排除しつつ merge_miss base に集約
    groups = defaultdict(list)
    seen = set()
    with FINAL.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] in seen:
                continue
            seen.add(r["rep"])
            if r["base_slug"] not in merge_bases:
                continue
            groups[r["base_slug"]].append(r)

    rows = []
    cat = defaultdict(int)
    for base, pages in groups.items():
        for p in pages:
            p["foreign"] = foreign.get(p["rep"]) is True
            p["v0"] = int(p["vols"] or 0) == 0
            p["latin"] = is_latin(p["title"])
        real = [p for p in pages if not p["foreign"] and not p["v0"]]
        n_foreign = sum(1 for p in pages if p["foreign"])
        n_v0 = sum(1 for p in pages if p["v0"])
        edition = any(EDITION_KW.search(p["title"]) for p in pages)
        titles = {norm_title(p["title"]) for p in real}
        authsets = [author_set(p["rep"], by_name) for p in real]
        distinct_auth = set().union(*authsets) if authsets else set()

        if base.strip() == "":
            disp = "C3_ORPHAN(空base=c-3で処理済)"
        elif len(real) < 2:
            disp = "RESOLVED_BY_DROP(外国版/v0除くと衝突解消)"
        elif edition:
            disp = "EDITION(版違い→版統合)"
        elif len(titles) == 1:
            # 同題: 著者集合が一致=merge / バラけ多数=雑誌? / 少数=要裁定
            same_auth = all(a == authsets[0] for a in authsets)
            if same_auth:
                disp = "MERGE_CANDIDATE(同題×同著者=断片)"
            elif len(distinct_auth) >= 5:
                disp = "ANTHOLOGY?(同題×別著者多数=雑誌drop疑い)"
            else:
                disp = "AUTHOR_SPLIT(同題×別著者少数=表記揺れ/option2要裁定)"
        else:
            disp = "DIFF_TITLE(別題×著者共有=option2/別漫画化/無関係要裁定)"

        cat[disp.split("(")[0]] += 1
        det = " || ".join(f"{p['title'][:14]}(v{p['vols']},{p['year'] or '—'}{',F' if p['foreign'] else ''}{',0' if p['v0'] else ''})" for p in pages)
        rows.append((disp, base, n_foreign, n_v0, len(real), det))

    with OUT.open("w", encoding="utf-8") as f:
        f.write("disposition\tbase\tn_foreign\tn_v0\tn_real\tpages\n")
        for x in sorted(rows):
            f.write("\t".join(str(v) for v in x) + "\n")

    print(f"=== gap c-2 merge漏れ {len(groups):,}群 の機械仕分け(merge無し・調査) → {OUT.name} ===")
    for k, v in sorted(cat.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
