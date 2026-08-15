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
import argparse, glob, json, os, sys, time, urllib.request, urllib.parse, urllib.error
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
        if isinstance(e, urllib.error.HTTPError) and e.code == 429:  # ★厳密判定(偽429対策2026-08-03)
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
# ★楽天ISBNキャッシュ(.cache/rakuten-isbn.jsonl 約370MB)からも caption を拾う (2026-07-26追加)。
#   これを見ていなかったため --live 無しでは材料が **38,981頁中5頁** しか集まらず、
#   「楽天に材料が無い」と誤認する状態だった。 既に手元にある内部データなので外部照会ゼロで使える。
#   形は {"isbn": "...", "item": {楽天itemそのまま}}。
#   ★2026-08-15 追加: **delta も読む**。 rakuten-isbn.jsonl(2026-06-18)だけを見ていたため
#   その後に収穫した rakuten-isbn-delta.jsonl(2026-06-28・828MB)の caption を丸ごと捨てていた。
#   実測(本番 catch空×2巻以上 13,257頁): 旧=材料が取れるのは180頁 → delta込みで365頁(+185)。
#   2026-07-26 の「キャッシュを見ていなかった」修正と同じ型の取りこぼし。
#   D: は外付けで不在のことがある(= [[d_drive_external_flaky]])ので存在する物だけ読む。
_CAP_SOURCES = [
    f"{ROOT}/.cache/rakuten-isbn.jsonl",
    f"{ROOT}/.cache/rakuten-isbn-delta.jsonl",
    "D:/mangal-cache/rakuten-isbn.jsonl",
    "D:/mangal-cache/rakuten-isbn-delta.jsonl",
]
_seen_src = set()
for rj in _CAP_SOURCES:
    if not os.path.exists(rj):
        continue
    _key = os.path.basename(rj)
    if _key in _seen_src:      # 同名(C:とD:のミラー)は片方だけ
        continue
    _seen_src.add(_key)
    _n = 0
    for l in open(rj, encoding="utf-8", errors="replace"):
        if '"itemCaption"' not in l:   # 高速スキップ(828MB×2を全部jsonl parseしない)
            continue
        try:
            r = json.loads(l)
        except Exception:
            continue
        ib = str(r.get("isbn") or "")
        cap = ((r.get("item") or {}).get("itemCaption") or "").strip()
        if ib and cap and ib not in pre:
            pre[ib] = cap
            _n += 1
    print(f"  楽天ISBNキャッシュ({_key})から caption {_n:,} 件")

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
