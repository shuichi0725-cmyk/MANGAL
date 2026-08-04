# -*- coding: utf-8 -*-
"""STRICT提案を種4(volumes-supplement-auto.yml)へ純粋追加。既定=dry-run、--applyで書込。
 - 発売日は楽天salesDateから日まで採る(不明なら YYYY-MM のまま。捏造しない)
 - series_keys は頁の既存ISBN→db-v2(volumes→editions→series)で結線。結線できない物は skip し報告
 - 既存seedのisbn13と重複する物は skip(純粋追加の保護)
 - changelog: data/seeds/intake-manifest/volgap-rakuten-local-changelog.jsonl に1行/件
"""
import os, sys, re, json, sqlite3, yaml, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
SEED = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
APPLY = "--apply" in sys.argv
TODAY = datetime.date.today().isoformat()

IN = sys.argv[sys.argv.index("--in") + 1] if "--in" in sys.argv else os.path.join(ROOT, ".cache", "volgap-rakuten-local2.json")
SRCTAG = sys.argv[sys.argv.index("--source") + 1] if "--source" in sys.argv else "rakuten-local"
rows = [r for r in json.load(open(IN, encoding="utf-8")) if r["tier"] == "STRICT"]
print(f"STRICT {len(rows)} 巻 / {len({r['stem'] for r in rows})} 頁", flush=True)

# --- 正確な salesDate を取り直す ---
want = {r["isbn"] for r in rows}
sd = {}
n = 0
for isbn, it in R.iter_items((R.DELTA, R.OLD)):
    n += 1
    if n % 300000 == 0:
        print(f"  ...{n:,}", flush=True)
    if isbn in want and isbn not in sd:
        sd[isbn] = it.get("salesDate", "")
print(f"salesDate 取得 {len(sd)}/{len(want)}", flush=True)


def date_of(isbn, fallback):
    t = R.parse_salesdate(sd.get(isbn, ""))
    if not t:
        return fallback
    y, m, d = t
    if m and d:
        return f"{y:04d}-{m:02d}-{d:02d}"
    if m:
        return f"{y:04d}-{m:02d}"
    return f"{y:04d}"


# --- series_key 結線 ---
con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
cur = con.cursor()


def norm_isbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def skeys_for_page(stem):
    d = yaml.safe_load(open(os.path.join(SRC, stem + ".yml"), encoding="utf-8")) or {}
    isbns = [norm_isbn(v.get("isbn13")) for e in (d.get("editions") or []) for v in (e.get("volumes") or []) if v.get("isbn13")]
    ks = set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id "
                             "JOIN series se ON se.id=e.series_id WHERE v.isbn13=?", (ib,)):
            ks.add(r[0])
    return sorted(ks)


seed = yaml.safe_load(open(SEED, encoding="utf-8")) or {}
existing = {str(e.get("isbn13") or "") for e in (seed.get("volumes") or [])}
print(f"既存seed entry {len(seed.get('volumes') or [])} / isbn {len(existing)}", flush=True)

new_entries, skipped_dup, skipped_nokey = [], [], []
cache_keys = {}
for r in rows:
    if r["isbn"] in existing:
        skipped_dup.append(r); continue
    if r["stem"] not in cache_keys:
        cache_keys[r["stem"]] = skeys_for_page(r["stem"])
    ks = cache_keys[r["stem"]]
    if not ks:
        skipped_nokey.append(r); continue
    new_entries.append({
        "series_keys": ks,
        "qid": None,
        "number": int(r["number"]),
        "isbn13": r["isbn"],
        "release_date": date_of(r["isbn"], r["date"]),
        "pages": None,
        "publisher": r["publisher"],
        "edition_type": r["etype"],
        "title_display": r.get("rakuten_title") or r.get("raw") or "",
        "source": SRCTAG,
        "added_at": TODAY,
        "note": f"巻抜けローカル楽天種fill slug={r['stem']} gate=題完全一致+版prefix{r['cand_prefix']}+日付整合+著者{r['author_ok']}",
    })

print(f"追加候補 {len(new_entries)} / dup skip {len(skipped_dup)} / series_key不明 skip {len(skipped_nokey)}")
if skipped_nokey:
    print("  series_key不明: " + ", ".join(sorted({r['stem'] for r in skipped_nokey})[:15]))

if not APPLY:
    print("dry-run(--apply で書込)")
    sys.exit(0)

seed.setdefault("volumes", []).extend(new_entries)
tmp = SEED + ".new"
with open(tmp, "w", encoding="utf-8") as f:
    yaml.safe_dump(seed, f, allow_unicode=True, sort_keys=False, width=10000)
chk = yaml.safe_load(open(tmp, encoding="utf-8"))
assert len(chk["volumes"]) == len(seed["volumes"]), "検証失敗"
os.replace(tmp, SEED)
print(f"種4auto: {len(seed['volumes'])} entry へ({len(new_entries)} 純粋追加)")

log = os.path.join(ROOT, "data", "seeds", "intake-manifest", "volgap-rakuten-local-changelog.jsonl")
os.makedirs(os.path.dirname(log), exist_ok=True)
with open(log, "a", encoding="utf-8") as f:
    for e, r in zip(new_entries, [x for x in rows if x["isbn"] not in existing and cache_keys.get(x["stem"])]):
        f.write(json.dumps({"at": TODAY, "op": "volgap-fill-rakuten-local", "slug": r["stem"],
                            "before": f"vol{r['number']}欠番", "after": f"vol{r['number']}={r['isbn']}",
                            "edition_type": r["etype"], "source": "rakuten-local-seed",
                            "gate": f"title-exact+pub{r['cand_prefix']}+date-in-range+author{r['author_ok']}"},
                           ensure_ascii=False) + "\n")
print(f"→ changelog {log}")
print("次: python scripts/_reflect-targeted.py --only <stems> で反映")
