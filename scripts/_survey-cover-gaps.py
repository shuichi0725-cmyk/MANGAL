"""書影のぬけ 調査: cover=空のページを、修正可能性で分類。

分類軸(fixability):
- fixable_now    : 巻ISBNのうち≥1がharvestに実書影(noimage以外)有 → 再join/再promoteで付く
- isbn_no_image  : ISBNはあるがharvestに実書影無(noimage/未収録) → Amazon等別ソース要 or 絶版
- no_isbn        : 巻にISBNが全く無い → まずISBN確定(種4/題照合)が要る

入力: data/manga-list-index.json(cover空ページ) + manga.v2 + 楽天harvest
出力: docs/cover-gap-survey.tsv + サマリ
"""
import sys, os, json, collections, yaml, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
ROOT = L.ROOT
COVER_SET_CACHE = f"{ROOT}/.cache/harvest-cover-isbns.json"


def norm_isbn(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def build_cover_set():
    """harvest全itemから 実書影(noimage以外 largeImageUrl)有 ISBN集合を構築(cache)。"""
    if os.path.exists(COVER_SET_CACHE):
        return set(json.load(open(COVER_SET_CACHE, encoding="utf-8")))
    have = set()
    n = 0
    for isbn, it in L.iter_items((L.DELTA, L.OLD)):
        n += 1
        if n % 200000 == 0:
            print(f"  ...{n:,} scanned", flush=True)
        cov = (it.get("largeImageUrl") or it.get("mediumImageUrl") or "")
        if cov and "noimage" not in cov:
            have.add(isbn)
    json.dump(sorted(have), open(COVER_SET_CACHE, "w", encoding="utf-8"))
    print(f"harvest実書影ISBN: {len(have):,}", flush=True)
    return have


def main():
    print("harvest cover-ISBN集合 構築/読込...", flush=True)
    cover_isbns = build_cover_set()
    print(f"  実書影ISBN {len(cover_isbns):,}", flush=True)

    d = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
    f = d["f"]; I = {k: f.index(k) for k in ["slug", "title", "cover", "total_volumes", "year_started"]}
    nocov = [r for r in d["d"] if not r[I["cover"]]]
    print(f"cover空ページ: {len(nocov):,} を manga.v2 で精査...", flush=True)

    rows = []
    cls = collections.Counter()
    for i, r in enumerate(nocov):
        if i % 2000 == 0:
            print(f"  ...{i}/{len(nocov)}", flush=True)
        slug = r[I["slug"]]
        p = f"{ROOT}/data/manga.v2/{slug}.yml"
        if not os.path.exists(p):
            continue
        try:
            m = yaml.safe_load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not m:
            continue
        isbns = []
        has_any_cover = False
        for ed in (m.get("editions") or []):
            for v in (ed.get("volumes") or []):
                if v.get("cover_url"):
                    has_any_cover = True
                if v.get("isbn13"):
                    isbns.append(norm_isbn(v["isbn13"]))
        if has_any_cover:
            continue  # 実際は書影あり(index古い)→除外
        n_isbn = len(isbns)
        n_fix = sum(1 for ib in isbns if ib in cover_isbns)
        if n_isbn == 0:
            kind = "no_isbn"
        elif n_fix > 0:
            kind = "fixable_now"
        else:
            kind = "isbn_no_image"
        cls[kind] += 1
        rows.append({
            "slug": slug, "title": str(r[I["title"]])[:30], "kind": kind,
            "n_vol": r[I["total_volumes"]] or 0, "n_isbn": n_isbn, "n_harvest_cover": n_fix,
            "year": r[I["year_started"]] or "",
        })

    rows.sort(key=lambda x: (x["kind"] != "fixable_now", -x["n_harvest_cover"], -x["n_vol"]))
    with open(f"{ROOT}/docs/cover-gap-survey.tsv", "w", encoding="utf-8", newline="") as fp:
        import csv
        w = csv.DictWriter(fp, fieldnames=["slug", "title", "kind", "n_vol", "n_isbn", "n_harvest_cover", "year"], delimiter="\t")
        w.writeheader(); w.writerows(rows)

    print(f"\n=== 書影ぬけ {len(rows):,} 分類 ===")
    for k in ["fixable_now", "isbn_no_image", "no_isbn"]:
        print(f"  {k:14}: {cls[k]:,}")
    print("\n出力: docs/cover-gap-survey.tsv")
    print("\n=== fixable_now sample (即修正可) ===")
    for x in [x for x in rows if x["kind"] == "fixable_now"][:12]:
        print(f"  {x['slug'][:34]:34} {x['n_harvest_cover']}/{x['n_isbn']}巻 書影有 ({x['year']}) {x['title']}")


if __name__ == "__main__":
    main()
