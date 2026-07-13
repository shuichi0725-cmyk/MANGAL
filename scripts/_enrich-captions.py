#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""キャッチ/詳細エンリッチの材料収集 (= skill enrich-catch-synopsis の Step1)

対象slugリストの全巻ISBNについて、楽天の紹介文(itemCaption)を キャッシュ→live の順で集め、
AI生成用の材料jsonlを書き出す。
  出力: .cache/enrich/materials.jsonl
    {slug, title, authors, genres_now, captions: [{vol, isbn, caption}], n_vols}
使い方:
  python scripts/_enrich-captions.py --slugs a,b,c [--src .preview-data/manga] [--live]
  python scripts/_enrich-captions.py --missing [--src DIR]   # catch/synopsis欠け頁を自動抽出
レート: live 1.2s/req・429即中断([[ndl_access_rate_method]]と同じ礼儀)。
"""
import argparse, glob, json, os, sys, time, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(f"{ROOT}/.cache/enrich", exist_ok=True)
OUT = f"{ROOT}/.cache/enrich/materials.jsonl"

ap = argparse.ArgumentParser()
ap.add_argument("--slugs")
ap.add_argument("--missing", action="store_true")
ap.add_argument("--src", default=".preview-data/manga")
ap.add_argument("--live", action="store_true")
ap.add_argument("--limit", type=int, default=10**9)
a = ap.parse_args()

env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
ORIGIN = env.get("RAKUTEN_REFERER", "").rstrip("/")

def live_caption(isbn):
    q = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "isbn": isbn, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}  # ★在庫切れ含む(旧刊必須 [[rakuten_out_of_stock_flag]])
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(q))
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        items = d.get("Items") or []
        return (items[0].get("itemCaption") or "").strip() if items else ""
    except Exception as e:
        if "429" in str(e):
            print("★429→中断"); sys.exit(2)
        return ""

# 予約行のcaption(タダで拾える分)
pre = {}
pj = f"{ROOT}/.cache/preorders/preorders-latest.jsonl"
if os.path.exists(pj):
    for l in open(pj, encoding="utf-8"):
        r = json.loads(l)
        if r.get("caption"):
            pre[r["isbn"]] = r["caption"]

targets = []
files = glob.glob(os.path.join(ROOT, a.src, "*.yml"))
for p in files:
    d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
    if not d:
        continue
    if a.slugs and d.get("slug") not in set(a.slugs.split(",")):
        continue
    if a.missing and d.get("catch") and d.get("synopsis"):
        continue
    if not a.slugs and not a.missing:
        continue
    targets.append((p, d))
targets = targets[: a.limit]
print(f"対象 {len(targets)}頁 (src={a.src}, live={a.live})")

fo = open(OUT, "w", encoding="utf-8")
n_live = 0
for p, d in targets:
    caps = []
    for e in d.get("editions") or []:
        for v in (e.get("volumes") or []):
            ib = str(v.get("isbn13") or "")
            if len(ib) != 13:
                continue
            cap = pre.get(ib, "")
            if not cap and a.live:
                cap = live_caption(ib)
                n_live += 1
                time.sleep(1.2)
            if cap:
                caps.append({"vol": v.get("number"), "isbn": ib, "caption": cap[:800]})
    caps.sort(key=lambda x: (x["vol"] is None, x["vol"]))
    fo.write(json.dumps({"slug": d.get("slug"), "title": d.get("title"),
                         "authors": [x.get("name") for x in (d.get("authors") or [])],
                         "genres_now": d.get("genres") or [], "demographic": d.get("demographic"),
                         "has_catch": bool(d.get("catch")), "has_synopsis": bool(d.get("synopsis")),
                         "n_vols": sum(len(e.get("volumes") or []) for e in d.get("editions") or []),
                         "captions": caps}, ensure_ascii=False) + "\n")
fo.close()
print(f"材料書出 → {OUT} (live照会 {n_live}回)")
