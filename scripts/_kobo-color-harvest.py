#!/usr/bin/env python3
"""電子カラー版柱①: 楽天Koboから「カラー版」全冊をharvestする(★全量版 2026-08-03)。

ユーザ裁定(2026-08-03)「明らかに取得数が少ない。カラー版だけで叩いて漫画を全部取得し、
アイドル運転時に差分を取得が望ましい」:
- 旧: title=カラー版 × コミック(101904) × 2ソートunion = 窓の上限~6,000 → 3,779冊で頭打ち。
  ★「フルカラー」(「版」なし表記。TL/BL/単話系に多い)が検索語に含まれず丸ごと漏れていた。
- 新(全量モード=引数なし):
  キーワード{カラー版, フルカラー} × ジャンル再帰分割 × 多ソートunion。
  Kobo APIは1クエリ3,000件(page100×30)が上限なので、スライスのcountが超える時は
  ①子ジャンル(GenreSearch APIで動的取得)に分割 → ②葉でも超える時は8ソートの窓union
  (±releaseDate/±itemPrice/sales/standard/reviewCount/reviewAverage = 最大24,000窓)。
  全体dedup=itemNumber。出力は全上書き。
- ★--delta(アイドル運転の差分モード): キーワードごとに新着降順を歩き、既知(itemNumber)に
  2ページ連続で全部当たったら停止→新規だけ追記。数十req・~数分。収集のみ(照合/buildはOpus)。

レート: _rate_gate("rakuten") でプロセス間直列化(他柱と並走可)。429はbackoff吸収(厳密判定ログ)。
出力: .cache/kobo-color-raw.jsonl (full=全上書き / --delta=追記)
"""
import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import _rate_gate  # 全柱共有の楽天グローバル間隔(並走合算429を防ぐ)

OUT = ROOT / ".cache" / "kobo-color-raw.jsonl"
GENRE_TREE = ROOT / ".cache" / "kobo-genre-tree.json"
TOP = "101904"  # コミック(ラノベ/実用のカラー版ノイズを入口で遮断)
KEYWORDS = ("カラー版", "フルカラー")  # フルカラー版/完全カラー版は「カラー版」が内包
SORTS = ("-releaseDate", "+releaseDate", "-itemPrice", "+itemPrice",
         "sales", "standard", "reviewCount", "reviewAverage")
KEEP = ("title", "subTitle", "seriesName", "author", "authorKana", "titleKana",
        "publisherName", "itemNumber", "itemUrl", "affiliateUrl", "largeImageUrl",
        "itemPrice", "salesDate", "koboGenreId", "salesType")

env = {}
for ln in open(ROOT / ".env.local", encoding="utf-8"):
    if "=" in ln:
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip()
RREF = env.get("RAKUTEN_REFERER", "https://github.com/")
_o = urlparse(RREF)
RORG = f"{_o.scheme}://{_o.netloc}"


def _call(ep, params, retries=4):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env.get("RAKUTEN_ACCESS_KEY", ""),
         "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "format": "json", "formatVersion": "2"}
    p.update(params)
    u = f"https://openapi.rakuten.co.jp/services/api/{ep}?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "Mozilla/5.0"})
    for at in range(retries):
        try:
            _rate_gate.wait("rakuten", 1.3)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if at == retries - 1:
                raise
            # ★429は厳密判定でログ(偽429対策の型 2026-08-03)。いずれもbackoffで吸収
            is429 = isinstance(e, urllib.error.HTTPError) and e.code == 429
            wait = (2, 10, 45)[min(at, 2)]
            print(f"  retry({'429' if is429 else e.__class__.__name__}) {wait}s...", flush=True)
            time.sleep(wait)


def kobo(params):
    return _call("Kobo/EbookSearch/20170426", dict(params, hits=30))


def genre_children(gid):
    """子ジャンル一覧(動的取得・.cacheに永続)。★失敗はキャッシュしない(2026-08-03実踏:
    誤version(20141010)の400を空リストで焼いてしまい、以後ずっと「子なし」扱いになった)。
    正しいversion=20131010(EbookSearchの20170426とは別)。失敗時は空=分割せず多ソートへ。"""
    tree = {}
    if GENRE_TREE.exists():
        tree = json.loads(GENRE_TREE.read_text(encoding="utf-8"))
    if gid in tree:
        return tree[gid]
    try:
        r = _call("Kobo/GenreSearch/20131010", {"koboGenreId": gid})
        kids = [c.get("koboGenreId") for c in (r.get("children") or []) if c.get("koboGenreId")]
    except Exception as e:
        print(f"  genre取得失敗({gid}): {e.__class__.__name__} → 分割なし(キャッシュせず)", flush=True)
        return []
    tree[gid] = kids
    GENRE_TREE.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    return kids


def add_items(items, seen, rows):
    n = 0
    for it in items:
        key = it.get("itemNumber") or it.get("itemUrl")
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({k: it.get(k) for k in KEEP})
        n += 1
    return n


def walk(kw, gid, sort, seen, rows):
    """1ソート窓を最後(または3,000上限)まで歩く。戻り=このスライスの総count。"""
    page, total = 1, None
    while page <= 100:
        r = kobo({"title": kw, "koboGenreId": gid, "sort": sort, "page": page})
        if total is None:
            total = r.get("count") or 0
        items = r.get("Items") or []
        if not items:
            break
        add_items(items, seen, rows)
        if page * 30 >= total:
            break
        page += 1
    return total or 0


def probe_count(kw, gid):
    r = kobo({"title": kw, "koboGenreId": gid, "page": 1})
    return r.get("count") or 0


def harvest_slice(kw, gid, seen, rows, depth=0):
    count = probe_count(kw, gid)
    pad = "  " * depth
    if count == 0:
        return
    if count <= 3000:
        print(f"{pad}{kw} × {gid}: count={count} → 1パス", flush=True)
        walk(kw, gid, "-releaseDate", seen, rows)
        return
    kids = genre_children(gid) if depth < 2 else []
    if kids:
        print(f"{pad}{kw} × {gid}: count={count} > 3,000 → 子{len(kids)}ジャンルへ分割", flush=True)
        for c in kids:
            harvest_slice(kw, c, seen, rows, depth + 1)
        # 保険: 子に拾われない所属の取りこぼしを親の新着窓で1パス回収
        walk(kw, gid, "-releaseDate", seen, rows)
        return
    # 葉(または深さ上限)でも3,000超 → 多ソートの窓union
    print(f"{pad}{kw} × {gid}: count={count} > 3,000(葉) → 多ソートunion", flush=True)
    before = len(rows)
    for s in SORTS:
        walk(kw, gid, s, seen, rows)
        got = len(rows) - before
        print(f"{pad}  sort={s}: 累計新規{got}/{count}", flush=True)
        if got >= count * 0.98:
            break


def load_existing():
    seen = set()
    if OUT.exists():
        for ln in io.open(OUT, encoding="utf-8"):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            key = r.get("itemNumber") or r.get("itemUrl")
            if key:
                seen.add(key)
    return seen


def delta(seen):
    """アイドル運転用の差分: 新着降順を既知に当たるまで歩いて追記(逐次保存)。"""
    n_new = 0
    with io.open(OUT, "a", encoding="utf-8", newline="\n") as f:
        for kw in KEYWORDS:
            stale_pages = 0
            page = 1
            while page <= 100 and stale_pages < 2:
                r = kobo({"title": kw, "koboGenreId": TOP, "sort": "-releaseDate", "page": page})
                items = r.get("Items") or []
                if not items:
                    break
                fresh: list = []
                add = add_items(items, seen, fresh)
                for row in fresh:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()  # 逐次保存(停止しても残る)
                n_new += add
                stale_pages = stale_pages + 1 if add == 0 else 0
                page += 1
            print(f"delta {kw}: {page - 1}ページ走査", flush=True)
    print(f"差分完了: 新規{n_new}冊 (累計{len(seen)}) → {OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", action="store_true", help="差分モード(新着だけ追記・アイドル運転用)")
    a = ap.parse_args()

    if a.delta:
        if not OUT.exists():
            print("raw が無い → まず全量(引数なし)を実行"); return 2
        delta(load_existing())
        return 0

    seen: set = set()
    rows: list = []
    for kw in KEYWORDS:
        harvest_slice(kw, TOP, seen, rows)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"完了: {len(rows)}冊 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
