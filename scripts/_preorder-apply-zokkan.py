#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約①続巻の種4自動追加 (= 2026-07-06 段階実行①)

classified.json の zokkan を volumes-supplement-auto.yml へ純粋追加。
ゲート: slug実在 / 巻番号必須(不明はworklist) / 同ISBN既登録skip / series_keys=db-v2逆引き成功必須。
出力: 追加件数 + touched slugリスト(.cache/preorders/zokkan-touched.json) + 不備worklist追記
"""
import json, os, sys, sqlite3, datetime
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
TODAY = datetime.date.today().isoformat()

cls = json.load(open(f"{ROOT}/.cache/preorders/classified.json", encoding="utf-8"))
doc = yaml.safe_load(open(AUTO, encoding="utf-8")) or {"volumes": []}
have = {str(v.get("isbn13")) for v in doc["volumes"]}
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)

def keys_for_slug(slug):
    """既存頁のISBNからseries_key群を逆引き(先頭数冊で十分)"""
    p = f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p):
        return None
    d = yaml.safe_load(open(p, encoding="utf-8"))
    ks = set()
    for e in d.get("editions") or []:
        for v in (e.get("volumes") or [])[:6]:
            if v.get("isbn13"):
                for r in con.execute("SELECT s.series_key FROM volumes v JOIN editions e2 ON v.edition_id=e2.id JOIN series s ON e2.series_id=s.id WHERE v.isbn13=?", (str(v["isbn13"]),)):
                    ks.add(r[0])
        if ks:
            break
    return sorted(ks) or None

added = 0
touched = set()
wl = []
key_cache = {}
for r in cls["zokkan"]:
    isbn, slug, vol = r["isbn"], r.get("_slug"), r.get("_vol")
    if isbn in have:
        continue
    if not slug:
        wl.append((isbn, r["title"], "slug無")); continue
    if vol is None:
        wl.append((isbn, r["title"], f"巻番号不明 slug={slug}")); continue
    if slug not in key_cache:
        key_cache[slug] = keys_for_slug(slug)
    ks = key_cache[slug]
    if not ks:
        wl.append((isbn, r["title"], f"series_key逆引き不可 slug={slug}")); continue
    rd = r.get("ym")
    if rd and r.get("day"):
        rd = f"{rd}-{r['day']:02d}"
    doc["volumes"].append({"series_keys": ks, "qid": None, "number": int(vol), "isbn13": isbn,
                           "release_date": rd, "pages": None, "publisher": r.get("publisher"),
                           "edition_type": "standard", "title_display": r.get("title"),
                           "source": "rakuten-preorder", "added_at": TODAY,
                           "note": f"楽天予約ハーベスト① slug={slug}"})
    have.add(isbn)
    touched.add(slug)
    added += 1

yaml.dump(doc, open(AUTO, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)
json.dump(sorted(touched), open(f"{ROOT}/.cache/preorders/zokkan-touched.json", "w"))
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "a", encoding="utf-8") as f:
    for isbn, title, why in wl:
        f.write(f"zokkan_hold\t{isbn}\t\t{str(title)[:40]}\t\t\t{why}\n")

# ★covers seed自動追記(2026-07-10 ユーザ指摘=新刊巻の書影忘れ): harvestの実URL書影を
#   data/seeds/covers.jsonl.gz へ純粋追加。promoteの_cover_forがnull書影を充填する経路に乗せる。
import gzip as _gz
_cp = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
_have = set()
try:
    for _l in _gz.open(_cp, "rt", encoding="utf-8"):
        try: _have.add(json.loads(_l).get("isbn13"))
        except Exception: pass
except Exception: pass
_added_cov = 0
with _gz.open(_cp, "at", encoding="utf-8") as _f:
    for _r in cls["zokkan"]:
        _c = _r.get("cover")
        if _c and "noimage" not in _c and _r.get("isbn") not in _have:
            _f.write(json.dumps({"isbn13": _r["isbn"], "cover_url": _c}, ensure_ascii=False) + "\n")
            _have.add(_r["isbn"]); _added_cov += 1
print(f"covers seed追記: {_added_cov}件(新刊書影)")
print(f"種4追加 {added} / 対象頁 {len(touched)} / 保留 {len(wl)} (worklist追記)")
