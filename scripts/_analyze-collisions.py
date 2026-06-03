"""slug衝突1,794群を ★著者(作画含む全著者qid)× レーベル/imprint の重なり で4象限分類 (read-only)。
本番前のslug de-collapse/merge判断の素材。 出力 = .cache/preprod/collision-quadrants/*.tsv + サマリ。

4象限:
  AUTH+LABEL : 著者overlap ∧ imprint(レーベル)overlap → ★最も「同一作/同franchise」濃厚(版違い/分裂/同作者続刊)
  AUTH only  : 著者overlap ∧ レーベル別 → 同作者の別出版社版/別作(出版社移籍・他社再刊)
  LABEL only : 著者別 ∧ レーベルoverlap → 同誌/同レーベルの別作(homonym or アンソロジー)
  NEITHER    : 著者別 ∧ レーベル別 → 純homonym(別作の同読み)
著者欠落(qid無)は AUTH判定不能 → UNKNOWN_AUTH。
"""
import json
import sys
import sqlite3
from functools import reduce
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "preprod" / "collision-quadrants"
OUT.mkdir(parents=True, exist_ok=True)


def title_of(key):
    n = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return n[-1] if n else key


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    col = json.load((ROOT / ".cache/preprod/collisions.json").open(encoding="utf-8"))
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    key2sid = {k: s for s, k in con.execute("SELECT id, series_key FROM series")}

    def info(key):
        sid = key2sid.get(key)
        if not sid:
            return frozenset(), frozenset(), []
        auq = frozenset(q for (q,) in con.execute(
            "SELECT m.qid FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id "
            "WHERE sa.series_id=? AND m.qid IS NOT NULL AND m.qid!=''", (sid,)))
        aun = [a for (a,) in con.execute(
            "SELECT m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id WHERE sa.series_id=?", (sid,))]
        imp = frozenset(i for (i,) in con.execute(
            "SELECT DISTINCT e.imprint FROM editions e WHERE e.series_id=? AND e.imprint!=''", (sid,)))
        return auq, imp, aun

    quad = {"AUTH+LABEL": [], "AUTH_only": [], "LABEL_only": [], "NEITHER": [], "UNKNOWN_AUTH": []}
    for c in col:
        pages = c["pages"]
        auqs, imps, auns = [], [], []
        for k in pages:
            aq, im, an = info(k)
            auqs.append(aq); imps.append(im); auns.append(an)
        ne_au = [a for a in auqs if a]
        auth_overlap = len(ne_au) == len(pages) and bool(reduce(lambda a, b: a & b, ne_au)) if ne_au else False
        ne_im = [i for i in imps if i]
        label_overlap = len(ne_im) >= 2 and bool(reduce(lambda a, b: a & b, ne_im)) if ne_im else False
        rec = {"slug": c["slug"], "n": len(pages),
               "titles": [title_of(k) for k in pages],
               "authors": ["/".join(sorted(set(a))[:2]) for a in auns],
               "imprints": ["/".join(sorted(i)[:1]) for i in imps]}
        if not ne_au or len(ne_au) < len(pages):
            quad["UNKNOWN_AUTH"].append(rec)
        elif auth_overlap and label_overlap:
            quad["AUTH+LABEL"].append(rec)
        elif auth_overlap:
            quad["AUTH_only"].append(rec)
        elif label_overlap:
            quad["LABEL_only"].append(rec)
        else:
            quad["NEITHER"].append(rec)

    print(f"slug衝突 {len(col)}群 の 著者×レーベル 4象限:")
    for k, v in quad.items():
        print(f"  {k:13}: {len(v):4}群 / {sum(r['n'] for r in v):5}ページ")
    for qk in quad:
        with (OUT / f"{qk}.tsv").open("w", encoding="utf-8") as f:
            for r in sorted(quad[qk], key=lambda x: -x["n"]):
                line = f"{r['slug']}\t{r['n']}\t" + " ┃ ".join(
                    f"{t}[{a}|{i}]" for t, a, i in zip(r["titles"], r["authors"], r["imprints"]))
                f.write(line + "\n")
    for qk in ("AUTH+LABEL", "AUTH_only", "LABEL_only", "NEITHER"):
        print(f"\n■ {qk} の例:")
        for r in sorted(quad[qk], key=lambda x: -x["n"])[:8]:
            ex = " ┃ ".join(f"{t[:14]}[{a[:8]}/{i[:8]}]" for t, a, i in
                            zip(r["titles"], r["authors"], r["imprints"]))[:140]
            print(f"   [{r['slug'][:22]}]×{r['n']}: {ex}")
    json.dump(quad, (OUT / "quadrants.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n→ .cache/preprod/collision-quadrants/*.tsv")


if __name__ == "__main__":
    main()
