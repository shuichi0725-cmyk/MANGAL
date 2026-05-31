"""成年判定 本単位(ISBN)調査 = 本道(種1 MADB の per-book 成年コミック)。

★成年判定は本(巻)単位。 MADB raw metadata101 の schema:contentRating="成年コミック"
が日本の権威18禁フラグ(per-ISBN)。 現 series.adult_score はシリーズ集約で粒度ロス。

本ツール:
  1. MADB raw から ISBN→成年 を抽出(キャッシュ .cache/madb-isbn-adult.tsv)
  2. 種2 volumes(isbn13)に紐付け → series 単位で 成年巻数/総巻数
  3. 突合: 現 adult_score / 種a isAdult(v14マッチ)と比較
     → 日本基準(MADB) vs 米基準(AniList) の差 + 粒度ロスを可視化

※調査専用。 種1/種2/種3/adult_score は一切変更しない。
"""
import json, csv, gzip, sqlite3, sys, re
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAW = ".cache/madb/metadata101-clean.json"
CACHE = Path(".cache/madb-isbn-adult.tsv")
S = {"S180", "S150", "S130", "S100"}


def extract_madb():
    """MADB raw → ISBN→(成年flag, title)。 キャッシュ。"""
    if CACHE.exists():
        d = {}
        with CACHE.open(encoding="utf-8") as f:
            for r in csv.reader(f, delimiter="\t"):
                if len(r) >= 2:
                    d[r[0]] = (r[1] == "1", r[2] if len(r) > 2 else "")
        print(f"[cache] ISBN→成年: {len(d):,}", flush=True)
        return d
    print("MADB raw 読込中(~1-2分)...", flush=True)
    data = json.load(open(RAW, encoding="utf-8"))
    recs = data if isinstance(data, list) else data.get("@graph", [])
    out = {}
    for r in recs:
        isbn = r.get("schema:isbn")
        if not isbn:
            continue
        isbn = str(isbn).replace("-", "").strip()
        cr = r.get("schema:contentRating", "")
        cr = cr if isinstance(cr, str) else ""
        desc = r.get("schema:description", "")
        desc = desc if isinstance(desc, str) else ""
        adult = ("成年コミック" in cr) or ("成年コミック" in desc)
        nm = r.get("schema:name", "")
        if isinstance(nm, list):
            nm = next((x for x in nm if isinstance(x, str)), "")
        out[isbn] = (adult, nm)
    with CACHE.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        for isbn, (ad, nm) in out.items():
            w.writerow([isbn, "1" if ad else "0", nm])
    n_adult = sum(1 for v in out.values() if v[0])
    print(f"抽出: {len(out):,} ISBN, うち成年 {n_adult:,}", flush=True)
    return out


def main():
    isbn_adult = extract_madb()

    con = sqlite3.connect(".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    # series_key → (成年巻, 総巻), via volumes.isbn13 → editions → series
    ser_adult = defaultdict(int); ser_total = defaultdict(int)
    for sk, isbn in con.execute("""
        SELECT s.series_key, v.isbn13
        FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE v.isbn13 IS NOT NULL
    """):
        i = str(isbn).replace("-", "").strip()
        ser_total[sk] += 1
        if isbn_adult.get(i, (False, ""))[0]:
            ser_adult[sk] += 1
    score = {sk: sc for sk, sc in con.execute("SELECT series_key, adult_score FROM series")}
    con.close()

    # series で 成年巻を1つ以上持つ = per-book基準で adult
    perbook_adult = {sk for sk in ser_total if ser_adult.get(sk, 0) > 0}
    cur_adult = {sk for sk, sc in score.items() if sc >= 3}
    print(f"\n=== per-book(MADB成年巻≥1) vs 現score>=3 ===")
    print(f"  per-book adult series: {len(perbook_adult):,}")
    print(f"  現 score>=3 adult series: {len(cur_adult):,}")
    print(f"  両方一致: {len(perbook_adult & cur_adult):,}")
    print(f"  ★per-bookのみ(現状漏れ): {len(perbook_adult - cur_adult):,}")
    print(f"  ★現状のみ(per-book非成年=作者/imprint由来): {len(cur_adult - perbook_adult):,}")

    # 混在シリーズ(一部巻だけ成年)
    mixed = [sk for sk in perbook_adult if ser_adult[sk] < ser_total[sk]]
    print(f"\n=== 粒度: 混在シリーズ(一部巻のみ成年)= {len(mixed):,} ===")
    print("  例(成年巻/総巻):")
    for sk in sorted(mixed, key=lambda k: -ser_total[k])[:8]:
        print(f"    {sk[:50]} : {ser_adult[sk]}/{ser_total[sk]}")

    # 日米差: v14マッチで MADB成年(日) vs 種a isAdult(米)
    a_adult = {}
    with gzip.open(".cache/anilist-manga-dump.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line); a_adult[e.get("id")] = bool(e.get("isAdult"))
    quad = Counter()
    with open(".cache/match-v14-all.tsv", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] not in S or not r["a_id"]:
                continue
            jp = r["s3_key"] in perbook_adult           # 日本基準(MADB per-book)
            us = a_adult.get(int(r["a_id"]), False)      # 米基準(AniList)
            quad[(jp, us)] += 1
    print(f"\n=== 日本(MADB本単位成年) vs 米(AniList isAdult)= v14マッチ ===")
    print(f"  日◯米◯(一致adult): {quad[(True,True)]:,}")
    print(f"  日✗米✗(一致非): {quad[(False,False)]:,}")
    print(f"  ★日✗米◯(米のみ=BL/TL等 米基準で広い): {quad[(False,True)]:,}")
    print(f"  ★日◯米✗(日のみ=米が flag漏れ): {quad[(True,False)]:,}")


if __name__ == "__main__":
    main()
