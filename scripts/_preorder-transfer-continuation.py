#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出荷前レビュー(_preorder-review.py)の CONTINUATION 行を種4へ転送する (= 2026-09-14 新設)

背景: レビューゲートが「既存頁の続巻を誤って新作ドラフト化した」と指摘した行は、
skill daily-distill の規定では「種4転送 or 新シリーズなので正」を人が裁定する。
転送は毎回手で yml を書いていたが、series_keys 逆引き・同巻番号ゲート・covers 追記を
取り違えやすいので _preorder-apply-zokkan.py と同じ実装を1本にまとめた。

使い方:
  python scripts/_preorder-transfer-continuation.py --stem <SRC stem> --isbn <isbn13> --vol <N> \
      [--date YYYY-MM-DD] [--publisher 社名] [--title 表示題] [--cover URL] [--note 根拠]
  ★--stem は manga.v2 のファイル名(公開slugではない)。公開slugを渡した場合は pub2stem で解決する。
  ★同ISBN既登録 / 同巻番号既在 は追加せず理由を出して終わる(=二重化の安全弁)。
"""
import argparse, datetime, json, os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTO = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
TODAY = datetime.date.today().isoformat()
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)


def load_pub2stem():
    m = {}
    p = os.path.join(ROOT, "data", "seeds", "slug-overrides.yml")
    d = yaml.safe_load(open(p, encoding="utf-8")) or {}
    ov = d.pop("overrides", {}) or {}
    for stem, pub in d.items():
        if isinstance(pub, str) and pub != stem:
            m[pub] = stem
    for stem, rec in ov.items():
        pub = (rec or {}).get("slug") if isinstance(rec, dict) else None
        if pub and pub != stem:
            m[pub] = stem
    return m


def resolve_stem(slug):
    if os.path.exists(f"{ROOT}/data/manga.v2/{slug}.yml"):
        return slug
    stem = load_pub2stem().get(slug)
    return stem if stem and os.path.exists(f"{ROOT}/data/manga.v2/{stem}.yml") else None


def keys_for_stem(stem):
    d = yaml.safe_load(open(f"{ROOT}/data/manga.v2/{stem}.yml", encoding="utf-8"))
    ks = set()
    for e in d.get("editions") or []:
        for v in (e.get("volumes") or [])[:6]:
            if v.get("isbn13"):
                for r in con.execute(
                    "SELECT s.series_key FROM volumes v JOIN editions e2 ON v.edition_id=e2.id "
                    "JOIN series s ON e2.series_id=s.id WHERE v.isbn13=?", (str(v["isbn13"]),)):
                    ks.add(r[0])
        if ks:
            break
    return sorted(ks) or None


def page_numbers(stem):
    d = yaml.safe_load(open(f"{ROOT}/data/manga.v2/{stem}.yml", encoding="utf-8")) or {}
    return {v["number"] for e in (d.get("editions") or []) if (e.get("type") or "standard") == "standard"
            for v in (e.get("volumes") or []) if isinstance(v.get("number"), int)}


ap = argparse.ArgumentParser()
ap.add_argument("--stem", required=True)
ap.add_argument("--isbn", required=True)
ap.add_argument("--vol", type=int, required=True)
ap.add_argument("--date")
ap.add_argument("--publisher")
ap.add_argument("--title")
ap.add_argument("--cover")
ap.add_argument("--note", default="")
a = ap.parse_args()

stem = resolve_stem(a.stem)
if not stem:
    sys.exit(f"NG: 頁が見つからない stem/slug={a.stem}")
doc = yaml.safe_load(open(AUTO, encoding="utf-8")) or {"volumes": []}
if str(a.isbn) in {str(v.get("isbn13")) for v in doc["volumes"]}:
    sys.exit(f"skip: 同ISBN既登録 {a.isbn}")
if a.vol in page_numbers(stem):
    sys.exit(f"skip: 同巻番号{a.vol}が頁のstandard版に既在 stem={stem}(版違い/二重登録を疑う)")
keys = keys_for_stem(stem)
if not keys:
    sys.exit(f"NG: series_key逆引き不可 stem={stem}")

ent = {"series_keys": keys, "number": a.vol, "isbn13": str(a.isbn),
       "release_date": a.date, "publisher": a.publisher, "edition_type": "standard",
       "title_display": a.title, "source": "rakuten-preorder",
       "added_at": TODAY, "note": a.note or f"出荷前レビューCONTINUATION裁定で種4転送(stem={stem})"}
doc["volumes"].append({k: v for k, v in ent.items() if v not in (None, "")})
yaml.dump(doc, open(AUTO, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=200)

if a.cover and "noimage" not in a.cover:
    import gzip
    cp = os.path.join(ROOT, "data", "seeds", "covers.jsonl.gz")
    have = set()
    for l in gzip.open(cp, "rt", encoding="utf-8"):
        try: have.add(json.loads(l).get("isbn13"))
        except Exception: pass
    if str(a.isbn) not in have:
        with gzip.open(cp, "at", encoding="utf-8") as f:
            f.write(json.dumps({"isbn13": str(a.isbn), "cover_url": a.cover}, ensure_ascii=False) + "\n")
        print("  covers seed追記")
print(f"種4追加 OK: stem={stem} vol={a.vol} isbn={a.isbn} series_keys={keys}")
