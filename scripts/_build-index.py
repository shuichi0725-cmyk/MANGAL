"""索引ビルダー(仕様v2)。公開YAML(.preview-data/manga 既定、本番は data/manga.v2)から
  A=マスターSQLite(.cache/mangal-index*.sqlite, works/volumes/authors/coverage)
  S1=検索索引 / S2=一覧索引 / S3=ホーム完成リスト  を public/idx/ に生成。
S1/S2/S3 は A から派生(源は1本)。再生成可=git追跡はこのレシピのみ。

usage: python scripts/_build-index.py [--data .preview-data/manga] [--out public/idx] [--db .cache/mangal-index-preview.sqlite]
"""
import os, sys, glob, json, sqlite3, argparse
try:
    import yaml
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L


def first_volume_date(d):
    best = None
    for ed in d.get("editions") or []:
        if ed.get("type") != "standard":
            continue
        for v in ed.get("volumes") or []:
            if v.get("number") == 1 and v.get("release_date"):
                rd = str(v["release_date"])
                if best is None or rd < best:
                    best = rd
    if best:
        return best
    # standard 1巻が無ければ全体最小
    ds = [str(v["release_date"]) for ed in d.get("editions") or [] for v in ed.get("volumes") or [] if v.get("release_date")]
    return min(ds) if ds else None


def cover_url(d):
    vols = [v for ed in d.get("editions") or [] for v in ed.get("volumes") or []]
    v1 = next((v for ed in d.get("editions") or [] for v in ed.get("volumes") or []
               if v.get("number") == 1 and v.get("cover_url")), None)
    if v1:
        return v1["cover_url"]
    for v in vols:
        if v.get("cover_url"):
            return v["cover_url"]
    return None


def primary_author(d):
    for a in d.get("authors") or []:
        if a.get("name"):
            return a["name"]
    for a in d.get("original_authors") or []:
        if a.get("name"):
            return a["name"]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=".preview-data/manga")
    ap.add_argument("--out", default="public/idx")
    ap.add_argument("--db", default=".cache/mangal-index-preview.sqlite")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(os.path.dirname(a.db), exist_ok=True)

    files = glob.glob(os.path.join(a.data, "*.yml"))
    print(f"読み込み: {len(files)} works from {a.data}")

    if os.path.exists(a.db):
        os.remove(a.db)
    con = sqlite3.connect(a.db)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE works(slug TEXT PRIMARY KEY, title TEXT, title_kana TEXT, title_romaji TEXT,
      subtitle TEXT, demographic TEXT, status TEXT, publisher_key TEXT, magazine_key TEXT,
      genres TEXT, genres_provisional INT, year_started INT, year_ended INT, first_volume_date TEXT,
      anilist_id INT, work_qid TEXT, author_qid TEXT, popularity INT, score REAL, adult_us INT,
      anime_adapted INT, synopsis_len INT, catch TEXT, volume_count INT, edition_count INT,
      isbn_count INT, isbn_missing INT, cover_count INT, cover_missing INT, has_cover INT, rep_cover TEXT,
      has_kana INT, has_romaji INT, has_synopsis INT, has_genres INT, has_full_isbn INT, has_anilist INT);
    CREATE TABLE volumes(work_slug TEXT, edition_type TEXT, edition_label TEXT, imprint TEXT,
      number INT, isbn13 TEXT, isbn_present INT, release_date TEXT, date_precision TEXT,
      cover_url TEXT, cover_present INT, asin TEXT);
    CREATE TABLE authors(name TEXT PRIMARY KEY, kana TEXT, romaji TEXT, work_count INT);
    CREATE TABLE work_authors(work_slug TEXT, author TEXT, role TEXT);
    """)

    s1, s2, all_rows = [], [], []
    author_count = {}
    author_meta = {}
    for f in files:
        try:
            d = yaml.load(open(f, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not d:
            continue
        slug = d.get("slug") or os.path.splitext(os.path.basename(f))[0]
        vols = [(ed, v) for ed in d.get("editions") or [] for v in ed.get("volumes") or []]
        isbn_count = sum(1 for _, v in vols if v.get("isbn13"))
        cover_count = sum(1 for _, v in vols if v.get("cover_url"))
        vc = len(vols)
        rep = cover_url(d)
        genres = d.get("genres") or []
        au = primary_author(d)
        kana = d.get("title_kana") or ""
        romaji = d.get("title_romaji") or ""
        syn_len = len(d.get("synopsis") or "")
        row = (slug, d.get("title"), kana, romaji, d.get("subtitle"),
               d.get("demographic"), d.get("status"), d.get("publisher"), d.get("magazine"),
               json.dumps(genres, ensure_ascii=False), 1 if d.get("genres_provisional") else 0,
               d.get("year_started"), d.get("year_ended"), first_volume_date(d),
               d.get("anilist_id"), d.get("work_wikidata_qid"), d.get("wikidata_qid"),
               d.get("popularity") or 0, d.get("score"), 1 if d.get("adult_us") else 0,
               1 if d.get("anime_adapted") else 0, syn_len, d.get("catch"),
               vc, len(d.get("editions") or []), isbn_count, vc - isbn_count,
               cover_count, vc - cover_count, 1 if cover_count else 0, rep,
               1 if kana else 0, 1 if romaji else 0, 1 if syn_len else 0,
               1 if genres else 0, 1 if (vc and isbn_count == vc) else 0, 1 if d.get("anilist_id") else 0)
        cur.execute("INSERT INTO works VALUES(%s)" % ",".join("?" * len(row)), row)
        for ed, v in vols:
            rd = str(v.get("release_date") or "")
            prec = "day" if len(rd) >= 10 else ("month" if len(rd) == 7 else ("year" if len(rd) == 4 else "none"))
            cur.execute("INSERT INTO volumes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (slug, ed.get("type"), ed.get("label"), ed.get("imprint"), v.get("number"),
                         v.get("isbn13"), 1 if v.get("isbn13") else 0, rd or None, prec,
                         v.get("cover_url"), 1 if v.get("cover_url") else 0, v.get("asin")))
        for akey in ("authors", "original_authors"):
            for x in d.get(akey) or []:
                nm = x.get("name")
                if not nm:
                    continue
                author_count[nm] = author_count.get(nm, 0) + 1
                author_meta.setdefault(nm, (x.get("kana") or "", x.get("romaji") or ""))
                cur.execute("INSERT INTO work_authors VALUES(?,?,?)", (slug, nm, x.get("role") or akey))

        # S1 検索索引(最小)
        s1.append({"slug": slug, "t": d.get("title"), "k": kana, "r": romaji, "a": au})
        # S2 一覧索引
        s2.append({"slug": slug, "t": d.get("title"), "a": au, "d": d.get("demographic"),
                   "g": genres, "pub": d.get("publisher"), "mag": d.get("magazine"),
                   "st": d.get("status"), "y": d.get("year_started"),
                   "p": d.get("popularity") or 0, "c": 1 if cover_count else 0})
        all_rows.append({"slug": slug, "t": d.get("title"), "a": au, "cover": rep,
                         "p": d.get("popularity") or 0, "y": d.get("year_started"),
                         "fvd": first_volume_date(d), "g": genres})

    for nm, c in author_count.items():
        km, rm = author_meta.get(nm, ("", ""))
        cur.execute("INSERT INTO authors VALUES(?,?,?,?)", (nm, km, rm, c))
    con.commit()

    # S3 ホーム完成リスト
    def slim(r):
        return {"slug": r["slug"], "t": r["t"], "a": r["a"], "cover": r["cover"]}
    popular = [slim(r) for r in sorted(all_rows, key=lambda x: -x["p"])[:60]]
    new = [slim(r) for r in sorted([r for r in all_rows if r["fvd"]], key=lambda x: x["fvd"], reverse=True)[:60]]
    by_genre = {}
    for g in sorted({g for r in all_rows for g in r["g"]}):
        gl = [slim(r) for r in sorted([r for r in all_rows if g in r["g"]], key=lambda x: -x["p"])[:24]]
        if gl:
            by_genre[g] = gl
    s3 = {"popular": popular, "new": new, "genres": by_genre}

    # 出力(プロトタイプはプレーンJSON。CDNが転送時gzip)
    json.dump(s1, open(os.path.join(a.out, "search.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(s2, open(os.path.join(a.out, "list.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(s3, open(os.path.join(a.out, "home.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    def kb(p):
        return os.path.getsize(p) // 1024
    print(f"A(SQLite) → {a.db}")
    print(f"S1 search.json: {len(s1)}件 {kb(os.path.join(a.out,'search.json'))}KB")
    print(f"S2 list.json  : {len(s2)}件 {kb(os.path.join(a.out,'list.json'))}KB")
    print(f"S3 home.json  : popular{len(popular)}/new{len(new)}/genres{len(by_genre)} {kb(os.path.join(a.out,'home.json'))}KB")
    # 被覆サマリ(A の coverage 即答デモ)
    tot = cur.execute("select count(*) from works").fetchone()[0]
    for col in ["has_cover", "has_synopsis", "has_genres", "has_kana", "has_full_isbn", "has_anilist"]:
        n = cur.execute(f"select count(*) from works where {col}=1").fetchone()[0]
        print(f"  被覆 {col:14}: {n}/{tot} ({n*100//max(1,tot)}%)")
    con.close()


if __name__ == "__main__":
    main()
