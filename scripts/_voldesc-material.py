#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巻説明(volume-desc)の材料収集 (= skill volume-desc の Step1)

対象slugの全巻ISBNについて楽天の紹介文(itemCaption+contents)を
キャッシュ(preorders→rakuten-isbn-delta 1パス)→live の順で集め、AI生成用の材料jsonlを書く。
  出力: .cache/voldesc/materials.jsonl
    {slug, title, authors, vols: [{vol, isbn, edition, caption, contents}], missing: [{vol, isbn, edition}]}
既に seed(data/seeds/volume-desc-ja.jsonl) に説明があるISBNは対象から除外(純粋追加運用)。
使い方:
  python scripts/_voldesc-material.py --slugs a,b,c [--live]
  python scripts/_voldesc-material.py --slugs-file list.txt [--live]   # 大量時(WinError206回避)
レート: live 1.2s/req・429即中断。
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as _L
except ImportError:
    from yaml import SafeLoader as _L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(f"{ROOT}/.cache/voldesc", exist_ok=True)
OUT = f"{ROOT}/.cache/voldesc/materials.jsonl"
SEED = f"{ROOT}/data/seeds/volume-desc-ja.jsonl"
DELTA = f"{ROOT}/.cache/rakuten-isbn-delta.jsonl"

ap = argparse.ArgumentParser()
ap.add_argument("--slugs")
ap.add_argument("--slugs-file")
ap.add_argument("--src", default="data/manga.v2")
ap.add_argument("--live", action="store_true")
ap.add_argument("--limit", type=int, default=10**9)
a = ap.parse_args()

slugs = []
if a.slugs:
    slugs = [s.strip() for s in a.slugs.split(",") if s.strip()]
if a.slugs_file:
    slugs += [s.strip() for s in open(a.slugs_file, encoding="utf-8") if s.strip()]
if not slugs:
    print("--slugs か --slugs-file を指定"); sys.exit(1)
slugs = slugs[: a.limit]

# 既seedのISBNは除外(純粋追加)
done = set()
if os.path.exists(SEED):
    for ln in open(SEED, encoding="utf-8"):
        try:
            done.add(json.loads(ln)["isbn13"])
        except Exception:
            pass

env = {}
for ln in open(f"{ROOT}/.env.local", encoding="utf-8"):
    ln = ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
ORIGIN = env.get("RAKUTEN_REFERER", "").rstrip("/")


def live_item(isbn):
    q = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
         "isbn": isbn, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(q))
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        items = d.get("Items") or []
        return items[0] if items else None
    except Exception as e:
        if "429" in str(e):
            print("★429→中断"); sys.exit(2)
        return None


# 対象巻の収集(slug→[{vol,isbn,edition}])
pages, want = {}, set()
for slug in slugs:
    p = os.path.join(ROOT, a.src, slug + ".yml")
    if not os.path.exists(p):
        # slug-override頁: slugフィールドで探す前にSRC名前提なので警告のみ
        print(f"  ! 見つからない: {slug} (SRC stem名で指定する)"); continue
    d = yaml.load(open(p, encoding="utf-8"), Loader=_L)
    vols = []
    for e in d.get("editions") or []:
        for v in (e.get("volumes") or []):
            ib = str(v.get("isbn13") or "")
            if len(ib) == 13 and ib not in done:
                vols.append({"vol": v.get("number"), "isbn": ib, "edition": e.get("type")})
                want.add(ib)
    pages[slug] = {"title": d.get("title"),
                   "authors": [x.get("name") for x in (d.get("authors") or [])],
                   "vols": vols}
print(f"対象 {len(pages)}頁 / 未生成ISBN {len(want)}件 (seed既存 {len(done)}件は除外)")

caps = {}  # isbn -> {"caption":..., "contents":...}

# 層1: 予約キャッシュ
pj = f"{ROOT}/.cache/preorders/preorders-latest.jsonl"
if os.path.exists(pj):
    for l in open(pj, encoding="utf-8"):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("isbn") in want and r.get("caption"):
            caps.setdefault(r["isbn"], {"caption": r["caption"], "contents": ""})

# 層2: rakuten-isbn-delta 1パス(830MB・requestedぶんだけ拾う)
rest = want - set(caps)
if rest and os.path.exists(DELTA):
    t0 = time.time()
    hit = 0
    for ln in open(DELTA, encoding="utf-8", errors="ignore"):
        m = re.match(r'^\{"isbn": ?"(\d{13})"', ln)
        ib = m.group(1) if m else None
        if ib is None or ib in caps or ib not in rest:
            continue
        try:
            item = json.loads(ln).get("item") or {}
        except Exception:
            continue
        cap = (item.get("itemCaption") or "").strip()
        if cap:
            caps[ib] = {"caption": cap, "contents": (item.get("contents") or "").strip()}
            hit += 1
    print(f"delta 1パス: hit {hit} ({time.time()-t0:.0f}秒)")

# 層3: live(残りだけ)
rest = sorted(want - set(caps))
if a.live and rest:
    print(f"live照会 {len(rest)}件 (~{len(rest)*1.2/60:.0f}分)")
    for i, ib in enumerate(rest):
        item = live_item(ib)
        if item:
            cap = (item.get("itemCaption") or "").strip()
            if cap:
                caps[ib] = {"caption": cap, "contents": (item.get("contents") or "").strip()}
        time.sleep(1.2)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(rest)}")

n_miss = 0
with open(OUT, "w", encoding="utf-8") as fo:
    for slug, pg in pages.items():
        vols, missing = [], []
        for v in pg["vols"]:
            c = caps.get(v["isbn"])
            if c:
                vols.append({**v, "caption": c["caption"], "contents": c["contents"]})
            else:
                missing.append(v)
        vols.sort(key=lambda x: (x["vol"] is None, x["vol"]))
        n_miss += len(missing)
        fo.write(json.dumps({"slug": slug, "title": pg["title"], "authors": pg["authors"],
                             "vols": vols, "missing": missing}, ensure_ascii=False) + "\n")
print(f"材料書出 → {OUT} (caption有 {len(caps)} / 材料なし {n_miss} = 欠落表へ)")
