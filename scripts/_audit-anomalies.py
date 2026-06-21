#!/usr/bin/env python3
"""
本番DB データ異常 広域監査 (READ-ONLY): manga.v2 を1パスで多カテゴリflag。
巻番号系(A/B/C)は別途完了済。ここは著者/年/文字化け/外国版/ジャンル/傑作集題/ISBN無 等。
出力: data/seeds/anomaly-<cat>.tsv + サマリ。
"""
import sys, glob, re, os, json, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""

PUBLISHERY = re.compile(r"(出版|書店|社$|刊行|編集部|プロダクション|スタジオ|製作委員会|新聞社|放送|テレビ|ＮＨＫ|NHK|株式会社|有限会社|コミックス?$|文庫$|BOOKS?$|books?$|編集$)")
PLACEHOLDER = re.compile(r"^(あ+|アンソロジー|名無し|不明|未定|未詳|ｱ+|[a-zＡ-Ｚ]$|[ぁ-ん]$|[ァ-ヶ]$|[0-9]+|[・、。…\-]+)$")
ROLE_SUFFIX = re.compile(r"[\s　](さく|作|著|画|漫画|まんが|原作|脚本|構成|原案|編|訳)$")
PUA = re.compile(r"[-\U000f0000-\U000ffffd\U00100000-\U0010fffd]")
COLLECTION = re.compile(r"(傑作集|傑作選|作品集|選集|短編集|短篇集|名作選|名作集|自選|セレクション|コレクション|大全集|全集)")

cats = {k: [] for k in ["author_publishery", "author_placeholder", "author_role_suffix", "author_unknown",
                        "year_bad", "pua_garbled", "title_latin", "isbn_foreign", "collection_title",
                        "genre_missing", "genre_other", "no_isbn_all"]}
n = 0
for fp in glob.glob("data/manga.v2/*.yml"):
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: continue
    if not isinstance(d, dict): continue
    n += 1
    slug = d.get("slug"); title = str(d.get("title") or "")
    aus = [str(a.get("name") or "") for a in (d.get("authors") or [])]
    oaus = [str(a.get("name") or "") for a in (d.get("original_authors") or [])]
    allau = aus + oaus
    for a in allau:
        if PUBLISHERY.search(a): cats["author_publishery"].append((slug, title, a)); break
    for a in allau:
        if PLACEHOLDER.match(a.strip()): cats["author_placeholder"].append((slug, title, a)); break
    for a in allau:
        if ROLE_SUFFIX.search(a): cats["author_role_suffix"].append((slug, title, a)); break
    if not aus or aus == ["(unknown)"]: cats["author_unknown"].append((slug, title, "/".join(aus)))
    ys, ye = d.get("year_started"), d.get("year_ended")
    if isinstance(ys, int) and (ys < 1900 or ys > 2030): cats["year_bad"].append((slug, title, f"start={ys}"))
    elif isinstance(ys, int) and isinstance(ye, int) and ye < ys: cats["year_bad"].append((slug, title, f"{ys}>{ye}"))
    blob = title + "/" + "/".join(allau) + "/" + str(d.get("synopsis") or "")
    if PUA.search(blob): cats["pua_garbled"].append((slug, title, "PUA有"))
    if title and re.fullmatch(r"[\x00-\x7f　 ]+", title) and re.search(r"[A-Za-z]", title): cats["title_latin"].append((slug, title, ""))
    if COLLECTION.search(title): cats["collection_title"].append((slug, title, ""))
    isbns = [to13(v.get("isbn13")) for e in (d.get("editions") or []) for v in (e.get("volumes") or []) if to13(v.get("isbn13"))]
    if isbns and all(not ib.startswith("9784") for ib in isbns): cats["isbn_foreign"].append((slug, title, isbns[0]))
    if not isbns: cats["no_isbn_all"].append((slug, title, f"{sum(len(e.get('volumes') or []) for e in (d.get('editions') or []))}巻"))
    gs = d.get("genres") or []
    if not gs: cats["genre_missing"].append((slug, title, ""))
    elif "other" in gs: cats["genre_other"].append((slug, title, ",".join(gs)))

os.makedirs("data/seeds", exist_ok=True)
print(f"走査 {n}ページ\n=== 異常カテゴリ ===")
for k, rows in sorted(cats.items(), key=lambda x: -len(x[1])):
    print(f"  {k}: {len(rows)}")
    with open(f"data/seeds/anomaly-{k}.tsv", "w", encoding="utf-8") as f:
        f.write("slug\ttitle\tdetail\n")
        for r in rows: f.write("\t".join(str(x) for x in r) + "\n")
print("\n--- 主要サンプル ---")
for k in ["author_publishery", "author_role_suffix", "author_placeholder", "pua_garbled", "year_bad", "isbn_foreign", "collection_title"]:
    print(f"[{k}] ({len(cats[k])})")
    for r in cats[k][:5]: print("   ", r[0], "|", r[1][:22], "|", r[2])
