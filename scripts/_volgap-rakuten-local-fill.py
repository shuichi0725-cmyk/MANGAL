# -*- coding: utf-8 -*-
"""【巻抜け × ローカル楽天種】欠番巻をローカル楽天harvestだけで埋める提案を作る(既定=dry-run)。

設計(慎重側に倒す):
 - 対象頁 = --list のstem一覧(既定=.cache/volgap-isbn-yes-lf.txt)。
 - gap = 各edition(type単位)の min..max の欠番。 union は取らない(版ごとに埋める先が違うため)。
 - 照合 = _rakuten_match_lib.build_index(巻トークンを剥がした残差題が頁題と完全一致のみ)。
 - ゲート4層:
    G1 既存ISBN除外: 本番全頁のISBN + 種2(db-v2)のISBN に在る物は候補にしない(取込もれでない=under-merge領域)
    G2 版一致: 候補の pub_key(ISBN登録者prefix, publisherName) が その版の主pub_key と一致
    G3 日付整合: 直前巻date <= 候補date <= 直後巻date (端は片側のみ)
    G4 drop題: promoteのdrop語(ガイド/画集/アンソロ等)を含む題は捨てる
 - 同一(base,vol)に複数printingがあれば最古を採用。
 - 出力: docs/production-diagnostics/volgap-rakuten-local.tsv (tier別) + .cache/volgap-rakuten-local.json
 - --apply で data/seeds/volumes-supplement-auto.yml へ純粋追加(STRICTのみ)。既定は書かない。

使用: python scripts/_volgap-rakuten-local-fill.py [--list PATH] [--apply]
"""
import os, sys, re, json, sqlite3, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
APPLY = "--apply" in sys.argv
LIST = sys.argv[sys.argv.index("--list") + 1] if "--list" in sys.argv else os.path.join(ROOT, ".cache", "volgap-isbn-yes-lf.txt")

DROP_WORDS = ["ガイドブック", "ファンブック", "設定資料集", "公式読本", "アンソロジー", "画集", "原画集",
              "大全集", "大百科", "大事典", "解体新書", "傑作選", "傑作集", "総集編", "名作集", "名作選",
              "ノベライズ", "小説", "アニメコミック", "劇場版", "攻略", "完全ガイド", "コミックガイド"]


def norm_isbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def load_pages(stems):
    pages = []
    for stem in stems:
        p = os.path.join(SRC, stem + ".yml")
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        pages.append((stem, d))
    return pages


def gaps_of(d):
    """[(edition_index, type, [missing numbers], {num: (date_tuple, isbn, publisher)})]"""
    out = []
    for i, e in enumerate(d.get("editions") or []):
        vols = [v for v in (e.get("volumes") or []) if v.get("number")]
        if len(vols) < 2:
            continue
        have = {}
        for v in vols:
            n = int(v["number"])
            dt = None
            rd = str(v.get("release_date") or "")
            m = re.match(r"(\d{4})-?(\d{2})?-?(\d{2})?", rd)
            if m:
                dt = (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))
            have.setdefault(n, (dt, norm_isbn(v.get("isbn13")), e.get("publisher") or ""))
        ns = sorted(have)
        miss = [n for n in range(ns[0], ns[-1] + 1) if n not in have]
        if miss:
            out.append((i, e.get("type") or "standard", miss, have, e))
    return out


def main():
    stems = [l.strip() for l in open(LIST, encoding="utf-8") if l.strip()]
    pages = load_pages(stems)
    print(f"対象頁 {len(pages)} / 入力 {len(stems)}", flush=True)

    # --- G1: 既存ISBN集合 ---
    prod_isbns = set()
    for stem, d in pages:
        pass
    # 本番全頁のISBN索引(鮮度優先で .cache/isbn-page-index.json を使う)
    idxp = os.path.join(ROOT, ".cache", "isbn-page-index.json")
    if os.path.exists(idxp):
        try:
            prod_isbns = set(json.load(open(idxp, encoding="utf-8")).keys())
        except Exception:
            prod_isbns = set()
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    db_isbns = {norm_isbn(r[0]) for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    print(f"既存ISBN: 本番索引 {len(prod_isbns)} / 種2 {len(db_isbns)}", flush=True)

    # --- 対象基底題 ---
    targets = {}
    for stem, d in pages:
        b = R.norm(R.nfkc(d.get("title", "")))
        if b:
            targets.setdefault(b, []).append(stem)
    print(f"基底題 {len(targets)} 種 → 楽天ローカル種を1パス走査(790MB+356MB)", flush=True)

    def prog(n):
        print(f"  ...{n:,} 件走査", flush=True)

    index, total = R.build_index(set(targets), progress=prog)
    print(f"走査 {total:,} item / 該当索引 {len(index)} キー", flush=True)

    rows = []
    for stem, d in pages:
        base = R.norm(R.nfkc(d.get("title", "")))
        for ei, etype, miss, have, e in gaps_of(d):
            # その版の主pub_key = 既存巻のISBN prefix + publisherName(楽天側)から推定
            have_isbns = [v[1] for v in have.values() if v[1]]
            pubprefixes = {}
            for ib in have_isbns:
                pubprefixes[ib[:7]] = pubprefixes.get(ib[:7], 0) + 1
            main_prefix = max(pubprefixes, key=pubprefixes.get) if pubprefixes else None
            ns = sorted(have)
            for n in miss:
                recs = R.recs_for(index, [base], n)
                if not recs:
                    continue
                # G4 drop題
                recs = [r for r in recs if not any(w in r["raw"] for w in DROP_WORDS)]
                # G1 既存ISBN
                recs = [r for r in recs if r["isbn"] not in prod_isbns and r["isbn"] not in db_isbns]
                if not recs:
                    continue
                # G2 版一致(ISBN登録者prefix)
                same_pub = [r for r in recs if main_prefix and r["isbn"][:7] == main_prefix]
                pool = same_pub or recs
                rec = min(pool, key=lambda r: r["date"])
                # G3 日付整合
                prevs = [have[x][0] for x in ns if x < n and have[x][0]]
                nexts = [have[x][0] for x in ns if x > n and have[x][0]]
                lo = max(prevs) if prevs else None
                hi = min(nexts) if nexts else None
                dt = rec["date"]
                date_ok = True
                if dt:
                    if lo and dt < lo:
                        date_ok = False
                    if hi and dt > hi:
                        date_ok = False
                else:
                    date_ok = False
                tier = "STRICT" if (same_pub and date_ok) else ("PUB_ONLY" if same_pub else ("DATE_ONLY" if date_ok else "WEAK"))
                rows.append({
                    "tier": tier, "stem": stem, "title": d.get("title", ""), "etype": etype,
                    "number": n, "isbn": rec["isbn"], "date": R.date_str(rec["date"]),
                    "publisher": rec["publisher"], "raw": rec["raw"], "cover": rec["cover"],
                    "main_prefix": main_prefix or "", "cand_prefix": rec["isbn"][:7],
                    "n_cands": len(recs),
                })

    order = {"STRICT": 0, "PUB_ONLY": 1, "DATE_ONLY": 2, "WEAK": 3}
    rows.sort(key=lambda r: (order[r["tier"]], r["stem"], r["number"]))
    outp = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-rakuten-local.tsv")
    with open(outp, "w", encoding="utf-8", newline="") as f:
        f.write("tier\tstem\ttitle\tetype\tnumber\tisbn\tdate\tpublisher\trakuten_title\tmain_prefix\tcand_prefix\tn_cands\n")
        for r in rows:
            f.write("\t".join(str(r[k]) for k in ("tier", "stem", "title", "etype", "number", "isbn", "date",
                                                  "publisher", "raw", "main_prefix", "cand_prefix", "n_cands")) + "\n")
    json.dump(rows, open(os.path.join(ROOT, ".cache", "volgap-rakuten-local.json"), "w", encoding="utf-8"), ensure_ascii=False)
    from collections import Counter
    c = Counter(r["tier"] for r in rows)
    print("=== 提案 ===")
    for t in ("STRICT", "PUB_ONLY", "DATE_ONLY", "WEAK"):
        print(f"  {t:9} {c.get(t,0)}")
    print(f"  合計 {len(rows)} 巻 / 対象頁 {len(set(r['stem'] for r in rows))}")
    print(f"→ {outp}")
    if APPLY:
        print("※ --apply は STRICT のみ 種4auto へ純粋追加(別途実装)")


if __name__ == "__main__":
    main()
