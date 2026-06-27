"""巻抜け(647) dry-run: 欠番の巻を楽天harvestから探し ISBN/発売日 候補を出す。
変更なし。種4(volumes-supplement.yml)補完の候補表を作る。

出力 docs/dryrun-volume-gaps.tsv:
  slug, vol, found(Y/N), cand_isbn, release_date, publisher, n_cand, rakuten_raw
"""
import sys, os, csv, pickle, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
ROOT = L.ROOT

def main():
    bundle = pickle.load(open(f"{ROOT}/.cache/rakuten-focus-index.pkl", "rb"))
    s2b = bundle["slug_to_bases"]
    rows = []
    with open(f"{ROOT}/docs/volume-gaps.tsv", encoding="utf-8") as fp:
        gaps = list(csv.DictReader(fp, delimiter="\t"))

    n_found = n_miss = 0
    slug_found = set()
    for g in gaps:
        sl = g["slug"]
        miss = [int(x) for x in g["missing"].split(",") if x.strip().isdigit()]
        bases = s2b.get(sl)
        if not bases:
            p = f"{ROOT}/data/manga.v2/{sl}.yml"
            if os.path.exists(p):
                d = yaml.safe_load(open(p, encoding="utf-8"))
                bases = {L.norm(d.get("title"))} if d else set()
            else:
                bases = set()
        for v in miss:
            recs = []
            for b in bases:
                recs += bundle["index"].get((b, v), [])
            recs = [r for r in recs if r["isbn"]]
            if recs:
                # 最古printing採用 (date有を優先)
                dated = [r for r in recs if r["date"]]
                rec = min(dated, key=lambda r: r["date"]) if dated else recs[0]
                n_found += 1; slug_found.add(sl)
                rows.append({
                    "slug": sl, "vol": v, "found": "Y", "cand_isbn": rec["isbn"],
                    "release_date": L.date_str(rec["date"], day=True),
                    "publisher": rec["publisher"], "n_cand": len(recs),
                    "rakuten_raw": rec["raw"],
                })
            else:
                n_miss += 1
                rows.append({"slug": sl, "vol": v, "found": "N", "cand_isbn": "", "release_date": "",
                             "publisher": "", "n_cand": 0, "rakuten_raw": ""})

    rows.sort(key=lambda r: (r["found"] != "Y", r["slug"], r["vol"]))
    with open(f"{ROOT}/docs/dryrun-volume-gaps.tsv", "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["slug", "vol", "found", "cand_isbn", "release_date", "publisher", "n_cand", "rakuten_raw"], delimiter="\t")
        w.writeheader(); w.writerows(rows)
    print(f"欠番総数: {n_found+n_miss}  found {n_found} / not-found {n_miss}")
    print(f"少なくとも1巻見つかったslug: {len(slug_found)}")
    print("\n=== found sample (先頭20) ===")
    for r in [r for r in rows if r["found"] == "Y"][:20]:
        print(f"  {r['slug'][:30]:30} v{r['vol']:>3} {r['cand_isbn']} {r['release_date']:>10} n{r['n_cand']} | {r['rakuten_raw'][:30]}")

if __name__ == "__main__":
    main()
