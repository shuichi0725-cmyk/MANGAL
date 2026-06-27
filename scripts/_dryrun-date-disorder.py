"""発売日逆行(515) dry-run: standard版の各巻に楽天最古salesDateを当て、
逆行(inversion)が減るかをシミュレート。変更は一切しない。

★edition-consistent(版整合): 単純な「全版横断の最古」は版混在を招き逆行を増やす
(例 sazae-san: 一部巻だけ1978姉妹社へ飛ぶ)。そこで各ページの「主版」
(= 最も多くの巻番号をカバーする publisher) を選び、**主版内の最古printing** を採る。
主版に無い巻は変更しない(=他版から日付を持ってこない)。

出力:
  docs/dryrun-date-disorder-summary.tsv : slug毎 inv_before/after, 変更数, 未マッチ数, 主版
  docs/dryrun-date-disorder-detail.tsv  : 変更候補の巻明細 (人手確認用 raw題付き)
"""
import sys, os, csv, pickle, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
ROOT = L.ROOT

def recs_for(bundle, bases, vol):
    """index から (bases × vol) の全printing records (date有) を返す。"""
    recs = []
    for b in bases:
        recs += bundle["index"].get((b, vol), [])
    return [r for r in recs if r["date"]]

def pub_key(rec):
    """publisher識別子 = ISBN登録者prefix(978-4-RRR) + publisherName。版を分ける。"""
    isbn = rec["isbn"]
    return (isbn[:7], rec.get("publisher", ""))

def primary_publisher(bundle, bases, vol_numbers):
    """このページの主版 = 最も多くの『巻番号』をカバーする pub_key。
    return (pub_key, {vol: oldest_rec_in_pub})。"""
    # pub_key -> set(vol) と pub_key -> {vol: [recs]}
    cover = {}
    perpub = {}
    for v in vol_numbers:
        for r in recs_for(bundle, bases, v):
            pk = pub_key(r)
            cover.setdefault(pk, set()).add(v)
            perpub.setdefault(pk, {}).setdefault(v, []).append(r)
    if not cover:
        return None, {}
    # カバー巻数 最大 → 同数なら古い方(初版edition)を優先
    def pubage(pk):
        recs = [r for vs in perpub[pk].values() for r in vs if r["date"]]
        return min((r["date"] for r in recs), default=(9999, 0, 0))
    best = max(cover, key=lambda pk: (len(cover[pk]), -pubage(pk)[0]))
    chosen = {}
    for v, recs in perpub[best].items():
        dated = [r for r in recs if r["date"]]
        if dated:
            chosen[v] = min(dated, key=lambda r: r["date"])
    return best, chosen

def inversions(seq):
    """seq=[(num, date_tuple|None)] num昇順前提。逆行ペア数。"""
    inv = 0
    prev = None
    for num, dt in seq:
        if dt is None:
            continue
        if prev is not None and dt < prev:
            inv += 1
        prev = dt
    return inv

def main():
    bundle = pickle.load(open(f"{ROOT}/.cache/rakuten-focus-index.pkl", "rb"))
    s2b = bundle["slug_to_bases"]
    slugs = []
    with open(f"{ROOT}/docs/volume-date-disorder.tsv", encoding="utf-8") as fp:
        for row in csv.DictReader(fp, delimiter="\t"):
            slugs.append(row["slug"])

    summ = []
    detail = []
    for sl in slugs:
        p = f"{ROOT}/data/manga.v2/{sl}.yml"
        if not os.path.exists(p): continue
        d = yaml.safe_load(open(p, encoding="utf-8"))
        if not d: continue
        bases = s2b.get(sl, {L.norm(d.get("title"))})
        # 最初の standard edition (auditと一致)
        ed = next((e for e in (d.get("editions") or []) if e.get("type") == "standard"), None)
        if not ed: continue
        vols = [(v.get("number"), L.parse_prod_date(v.get("release_date")), v.get("release_date"))
                for v in (ed.get("volumes") or []) if v.get("number")]
        vols.sort(key=lambda x: x[0])
        if len(vols) < 5: continue

        cur_seq = [(n, dt) for n, dt, _ in vols]
        inv_before = inversions(cur_seq)

        # 主版を選び、主版内の最古printingで日付を整える
        best_pub, chosen = primary_publisher(bundle, bases, [n for n, _, _ in vols])
        new_seq = []
        n_change = n_matched = n_unmatched = 0
        for n, dt, rawdate in vols:
            rec = chosen.get(n)
            if rec is None:
                n_unmatched += 1
                new_seq.append((n, dt))
                continue
            n_matched += 1
            old = rec["date"]
            # 主版最古が現状より前なら採用(=再版日を初版日に正規化)
            if old and (dt is None or old < dt):
                new_seq.append((n, old))
                n_change += 1
                detail.append({
                    "slug": sl, "vol": n,
                    "current": rawdate or "", "proposed": L.date_str(old, day=True),
                    "oldest_isbn": rec["isbn"], "n_cand": len(recs_for(bundle, bases, n)),
                    "rakuten_raw": rec["raw"], "rk_salesDate": rec["salesDate"],
                })
            else:
                new_seq.append((n, dt))
        inv_after = inversions(new_seq)
        summ.append({
            "slug": sl, "title": str(d.get("title"))[:24],
            "std_vols": len(vols), "inv_before": inv_before, "inv_after": inv_after,
            "fixed": inv_before - inv_after, "n_change": n_change,
            "matched": n_matched, "unmatched": n_unmatched,
            "primary_pub": (best_pub[1] or best_pub[0]) if best_pub else "",
        })

    summ.sort(key=lambda x: (-(x["fixed"]), -x["inv_before"]))
    with open(f"{ROOT}/docs/dryrun-date-disorder-summary.tsv", "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["slug", "title", "std_vols", "inv_before", "inv_after", "fixed", "n_change", "matched", "unmatched", "primary_pub"], delimiter="\t")
        w.writeheader(); w.writerows(summ)
    with open(f"{ROOT}/docs/dryrun-date-disorder-detail.tsv", "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["slug", "vol", "current", "proposed", "oldest_isbn", "n_cand", "rakuten_raw", "rk_salesDate"], delimiter="\t")
        w.writeheader(); w.writerows(detail)

    tot_before = sum(x["inv_before"] for x in summ)
    tot_after = sum(x["inv_after"] for x in summ)
    fully = sum(1 for x in summ if x["inv_after"] == 0 and x["inv_before"] > 0)
    improved = sum(1 for x in summ if x["fixed"] > 0)
    worse = sum(1 for x in summ if x["fixed"] < 0)
    print(f"slug処理: {len(summ)}")
    print(f"逆行総数: before {tot_before} -> after {tot_after}  (削減 {tot_before-tot_after})")
    print(f"改善slug {improved} / 完全解消 {fully} / 悪化 {worse}")
    print(f"変更候補巻 {len(detail)}")
    print("\n=== 改善Top20 ===")
    for x in summ[:20]:
        print(f"  {x['slug'][:34]:34} inv {x['inv_before']:>3}->{x['inv_after']:>3} chg{x['n_change']:>3} unm{x['unmatched']:>3} {x['title']}")
    if worse:
        print("\n=== 悪化 (要確認) ===")
        for x in summ:
            if x["fixed"] < 0: print(f"  {x['slug']} {x['inv_before']}->{x['inv_after']}")

if __name__ == "__main__":
    main()
