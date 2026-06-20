#!/usr/bin/env python3
"""
一覧用 軽量索引を生成 (= data/manga-list-index.json)。
一覧/トップ/フィルタ/カードが必要とする slim フィールドのみ + cover/total_volumes を事前計算。
editions/volumes全体・synopsis・tags・credits・alternative_titles 等の重い部分は除外 = props/転送を軽量化。
loadData.loadMangaListIndex() がこれを読む。検証(loadData)は別途 manga.v2 を読む promote が担保。
"""
import sys, json, glob, time, os
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L

# loadData が manga を弾く条件と同じ master キーで「表示対象」を絞る
DATA = os.environ.get("MANGAL_DATA_DIR", "data")
def load_keys(fn):
    p = os.path.join(DATA, fn)
    if not os.path.exists(p): p = os.path.join("data", fn)
    parsed = yaml.load(open(p, encoding="utf-8"), Loader=L) or {}
    # master は dict 形式 {key: {name:...}} (= loadData の Object.entries と同じ)
    if isinstance(parsed, dict): return set(parsed.keys())
    return set(x.get("key") for x in parsed if isinstance(x, dict))
pubKeys = load_keys("publishers.yml")
genreKeys = load_keys("genres.yml")
magKeys = load_keys("magazines.yml")

def cover_of(d):
    # primaryVolume相当: standard edition の number最小、無ければ全edition先頭の cover_url
    best = None
    for e in (d.get("editions") or []):
        for v in (e.get("volumes") or []):
            if v.get("cover_url"):
                return v["cover_url"]  # 最初に見つかった表紙(loadData coverUrlと同等の近似)
    return None

# 引数: [1]=src manga ディレクトリ (既定 data/manga.v2)、 [2]=出力ディレクトリ (既定 DATA)。
#   プレビュー用: python _build-list-index.py .preview-data/manga public
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, "manga.v2")
if not os.path.isdir(src): src = "data/manga.v2"
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else DATA
t0 = time.time(); idx = []; sidx = []; skipped = 0
for f in glob.glob(os.path.join(src, "*.yml")):
    try: d = yaml.load(open(f, encoding="utf-8"), Loader=L)
    except: skipped += 1; continue
    if not d: skipped += 1; continue
    # loadData と同じ表示ガード(必須欄/master外キーは一覧にも出さない=整合)
    if not (d.get("slug") and d.get("title") and d.get("title_kana") and d.get("title_romaji")
            and d.get("authors") and d.get("year_started")):
        skipped += 1; continue
    pub = d.get("publisher")
    if pub != "(unknown)" and pub not in pubKeys: skipped += 1; continue
    if any(p not in pubKeys for p in (d.get("publishers") or [])): skipped += 1; continue
    if d.get("magazine") and d["magazine"] not in magKeys: skipped += 1; continue
    gs = d.get("genres") or []
    if not gs or any(g not in genreKeys for g in gs): skipped += 1; continue
    eds = d.get("editions") or []
    tv = sum(len(e.get("volumes") or []) for e in eds)
    maxev = max((len(e.get("volumes") or []) for e in eds), default=0)
    latest = ""
    for e in eds:
        for v in (e.get("volumes") or []):
            rd = v.get("release_date")
            if rd and str(rd) > latest: latest = str(rd)
    aus = d.get("authors") or []
    oaus = d.get("original_authors") or []
    # ① 一覧索引(表示用) = 検索専用フィールド(title_romaji/alternative_titles/credits)は持たない
    idx.append({
        "slug": d["slug"], "title": d["title"], "title_kana": d["title_kana"],
        "subtitle": d.get("subtitle"),
        "cover": cover_of(d),
        "year_started": d["year_started"], "year_ended": d.get("year_ended"),
        "status": d.get("status"), "catch": d.get("catch"),
        "authors": [{"name": a.get("name"), "role": a.get("role"), "kana": a.get("kana") or ""} for a in aus],
        "original_authors": [{"name": a.get("name"), "kana": a.get("kana") or ""} for a in oaus],
        "genres": gs, "demographic": d.get("demographic"),
        "publisher": pub, "publishers": d.get("publishers") or [],
        "magazine": d.get("magazine"), "awards": d.get("awards"),
        "anime_adapted": d.get("anime_adapted"),
        "total_volumes": tv, "max_edition_volumes": maxev,
        "latest_date": latest[:7] if latest else None,
        "popularity": d.get("popularity"), "score": d.get("score"),
    })
    # ② 検索索引(検索専用) = matchText が必要とする text のみ (= 検索時だけ遅延ロード)
    alt = d.get("alternative_titles") or {}
    sidx.append({
        "slug": d["slug"], "title": d["title"], "title_kana": d["title_kana"],
        "title_romaji": d["title_romaji"],
        "alt": [v for v in [alt.get("en"), alt.get("fr"), alt.get("de"), alt.get("it"), alt.get("pt")] if v],
        "au": [a.get("name") for a in aus if a.get("name")]
              + [a.get("name") for a in oaus if a.get("name")]
              + [c.get("name") for c in (d.get("credits") or []) if c.get("name")],
    })
idx.sort(key=lambda x: (x["year_started"], x["title"]))
out = os.path.join(OUTDIR, "manga-list-index.json")
json.dump(idx, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
sout = os.path.join(OUTDIR, "manga-search-index.json")
json.dump(sidx, open(sout, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
mb = os.path.getsize(out) / 1e6
smb = os.path.getsize(sout) / 1e6
print(f"一覧索引: {len(idx)}作品 / {mb:.1f}MB → {out}")
print(f"検索索引: {len(sidx)}作品 / {smb:.1f}MB → {sout}")
print(f"(skip {skipped}) / {time.time()-t0:.1f}秒")
