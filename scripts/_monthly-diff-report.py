#!/usr/bin/env python3
"""月次 Phase1 差分レポート: 新 MADB dump を種2(db-v2)と突合し純増を集計。
純粋な読み取り専用。DBもseedも一切書き換えない。"""
import sys, sqlite3, ijson, json, datetime

DUMP = sys.argv[1] if len(sys.argv) > 1 else ".cache/madb/metadata101-1.2.18.json"
DB = ".cache/db-v2.sqlite"
TODAY = "2026-07-24"


def norm_isbn(s):
    if not s:
        return None
    d = "".join(ch for ch in str(s) if ch.isdigit())
    return d or None


def first_str(v):
    """schema:name 等が list/[{@value}] 混在。最初の素の文字列を返す。"""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("@value")
    if isinstance(v, list):
        for x in v:
            if isinstance(x, str):
                return x
            if isinstance(x, dict) and "@value" in x:
                return x["@value"]
    return None


print("[1/3] loading db-v2 sets ...", flush=True)
db = sqlite3.connect(DB)
c = db.cursor()
have_ids = set(r[0] for r in c.execute("SELECT madb_book_id FROM volumes WHERE madb_book_id IS NOT NULL"))
have_isbn = set(norm_isbn(r[0]) for r in c.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL"))
have_isbn.discard(None)
print(f"    db-v2: {len(have_ids)} madb_book_ids, {len(have_isbn)} isbn13", flush=True)

print(f"[2/3] streaming {DUMP} ...", flush=True)
total = 0            # class:MangaBook records
new_id = 0           # madb_book_id 未登録
new_id_new_isbn = 0  # 新id かつ 新isbn (真の純増)
new_id_dup_isbn = 0  # 新id だが既存isbn (=別ID再登録=虚構推理型 → 監査対象)
new_id_no_isbn = 0   # 新id かつ isbn空
adultish = 0         # contentRating==成年コミック (概算・4層filter前)
future = 0           # datePublished が未来 (予約/末尾)
new_creators = set()
modified_recent = 0  # 既存idで dateModified が最近 (訂正の可能性・上限)
sample_new = []

with open(DUMP, "rb") as f:
    for rec in ijson.items(f, "@graph.item"):
        t = rec.get("@type", "")
        if isinstance(t, list):
            t = ",".join(t)
        if "MangaBook" not in str(t):
            continue
        total += 1
        if total % 100000 == 0:
            print(f"    ...{total} records", flush=True)
        mid = rec.get("schema:identifier") or None
        isbn = norm_isbn(rec.get("schema:isbn"))
        cr = rec.get("schema:contentRating") or ""
        if isinstance(cr, str) and "成年" in cr:
            adultish += 1
        dp = rec.get("schema:datePublished") or ""
        if isinstance(dp, str) and dp > TODAY:
            future += 1
        is_new = mid is not None and mid not in have_ids
        if is_new:
            new_id += 1
            cre = rec.get("dcterms:creator")
            if isinstance(cre, dict):
                new_creators.add(cre.get("@id"))
            elif isinstance(cre, list):
                for x in cre:
                    if isinstance(x, dict):
                        new_creators.add(x.get("@id"))
            if not isbn:
                new_id_no_isbn += 1
            elif isbn in have_isbn:
                new_id_dup_isbn += 1
            else:
                new_id_new_isbn += 1
            if len(sample_new) < 15:
                sample_new.append((mid, isbn, first_str(rec.get("schema:name")), dp, rec.get("schema:volumeNumber")))
        else:
            # 既存id の訂正検知(上限概算): dateModified を持つ全件を後で使う想定
            pass

print(f"[3/3] done. total MangaBook records in dump: {total}", flush=True)
print()
print("=== Phase1 差分レポート (1.2.17 → 1.2.18) ===")
print(f"  種2 現況(db-v2): volumes madb_book_id={len(have_ids)} / isbn13={len(have_isbn)}")
print(f"  dump総 MangaBook: {total}")
print(f"  ── 新規 madb_book_id (未登録): {new_id}")
print(f"       ├ 新id×新ISBN (真の純増候補): {new_id_new_isbn}")
print(f"       ├ 新id×既存ISBN (別ID再登録=虚構推理型・要監査): {new_id_dup_isbn}")
print(f"       └ 新id×ISBN空: {new_id_no_isbn}")
print(f"  新規 creator(C-id, 概算): {len(new_creators)}")
print(f"  成年コミック概算(contentRating, 4層filter前): {adultish}")
print(f"  未来日付(予約/末尾検出候補): {future}")
print()
print("=== 新規サンプル (mid, isbn, name, date, vol) ===")
for s in sample_new:
    try:
        print("   ", s)
    except Exception:
        print("    <unprintable>", s[0], s[1])

json.dump({
    "from": "1.2.17", "to": "1.2.18",
    "dump_total_mangabook": total,
    "new_madb_book_id": new_id,
    "new_id_new_isbn": new_id_new_isbn,
    "new_id_dup_isbn": new_id_dup_isbn,
    "new_id_no_isbn": new_id_no_isbn,
    "new_creators_est": len(new_creators),
    "adultish_est": adultish,
    "future_dated": future,
}, open(".cache/monthly-diff-1.2.18.json", "w"), ensure_ascii=False, indent=1)
print()
print("saved -> .cache/monthly-diff-1.2.18.json")
