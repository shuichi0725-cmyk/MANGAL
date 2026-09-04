#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""発売日の鮮度監査 (= 「すてごろブッチ型」。 2026-09-04 ユーザ発見)

★なぜ要るか
  予約(未発売)の巻は **後から発売日が動く**(延期・前倒し)。 こちらの値は
  **ハーベストした日のまま**で、 追随する機構がどこにも無かった。
  実例: すてごろブッチ! (9784091543295) = 2026-07-09 に予約ハーベストで 2026-08-28 を取り、
        本番はその値のまま。 楽天の現在値は **2026-09-28**(1か月延期) = 頁が1週間ずれて
        「発売済のはずなのに書影が仮のまま」に見えた(ユーザ報告の入口)。

★根因は2層
  ① 追随機構が無い (= 本 script が埋める層)。
  ② ★promote の **予約頁合流ブロックに release-date-override が通っていない**
     (= cover-override / genre / magazine は通すのに日付だけ抜けていた。 予約頁は本流を
       通らない、 という既知の穴の同型 4件目)。 → `_promote-bulk-v2.py` 側で結線済。

★機械証拠は既に手元にある(= live を叩かない)
  日次の楽天予約ハーベスト `.cache/preorders/preorders-latest-full.jsonl`
  (= 漫画ジャンル 001001 の 未来〜今日 全量・最新スナップショット) を 1パスで読み、
  本番 `data/manga.v2` の release_date と ISBN で突合するだけで大半が出る。
  ハーベストに居ない未発売巻だけ `--live` で楽天に問い合わせる(1.3s/req・429即中断)。

分類:
  POSTPONED   本番 < 楽天 (= 延期)。 主対象。
  ADVANCED    本番 > 楽天 (= 前倒し / 本番側が未来過ぎ)。
  MINOR       |差| <= --minor-days (既定3日)。 ★奥付日 vs 店頭日の既知ゆれ = 自動適用しない。
  NOT_LISTED  本番が未発売なのに楽天のハーベストにも live にも無い (= 中止/取扱終了/ジャンル外)。
  NO_DATE     楽天側が「年月のみ」「発売日未定」。

★層(fix_layer)も出す: 発売日 override が **効かない経路がある**([[release_date_change_side_effects]])。
  PREORDER  = data/seeds/preorder-pages/<stem>.yml がある     → override + 予約合流の結線で効く
  SEED4     = volumes-supplement(-auto).yml に ISBN がある     → ★seed 本体を直す
  CANONICAL = edition-canonical/<stem>.yml がある              → ★seed 本体を直す
  OVERRIDES = edition-overrides.json に公開slugキーがある      → ★seed 本体を直す
  SEED2     = 上記なし                                        → override で効く

出力: docs/production-diagnostics/preorder-date-drift.tsv

使い方:
  python scripts/_audit-preorder-date-drift.py                    # ハーベスト証拠だけ(数分)
  python scripts/_audit-preorder-date-drift.py --live --limit 300 # 未掲載分を楽天に問い合わせ
  python scripts/_audit-preorder-date-drift.py --since 2026-01-01
"""
import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import yaml
_YL = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

SRC = os.path.join(ROOT, "data", "manga.v2")
PREORDER_DIR = os.path.join(ROOT, "data", "seeds", "preorder-pages")
CANON_DIR = os.path.join(ROOT, "data", "seeds", "edition-canonical")
HARVEST = os.path.join(ROOT, ".cache", "preorders", "preorders-latest-full.jsonl")
HARVEST_PREV = os.path.join(ROOT, ".cache", "preorders", "preorders-prev.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-date-drift.tsv")
LIVE_CACHE = os.path.join(ROOT, ".cache", "preorder-date-drift-live.json")

RE_SALES = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
RE_SALES_YM = re.compile(r"(\d{4})年(\d{1,2})月")
RE_SALES_Y = re.compile(r"(\d{4})年")


def norm_isbn(s) -> str:
    return re.sub(r"[^0-9X]", "", str(s or "")).upper()


def parse_sales(sd: str):
    """楽天 salesDate → (iso, precision)。 precision = day/day~/month/year/none
    ★「2027年01月26日頃」の **頃** = 楽天側も日付を確定できていない印(ハーベストの43%が これ)。
      日付としては採るが precision を day~ にして表に残す。 ★これ単独では不採用にしない
      (実測: 頃つき10件のうち8件は NDL が同じ日を持つ = 実在の予定日)。"""
    sd = str(sd or "")
    approx = "頃" in sd or "旬" in sd
    m = RE_SALES.search(sd)
    if m:
        return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups()), ("day~" if approx else "day")
    m = RE_SALES_YM.search(sd)
    if m:
        return "%04d-%02d" % tuple(int(x) for x in m.groups()), "month"
    m = RE_SALES_Y.search(sd)
    if m:
        return m.group(1), "year"
    return None, "none"


def days_between(a: str, b: str):
    """両方が YYYY-MM-DD の時だけ日数差(b - a)。 それ以外は None。"""
    try:
        ya, ma, da = (int(x) for x in a.split("-"))
        yb, mb, db = (int(x) for x in b.split("-"))
    except Exception:
        return None
    return (date(yb, mb, db) - date(ya, ma, da)).days


# ---------------- 本番側の走査 ----------------

def iter_volumes(page: dict):
    """editions[].volumes / editions[].versions[].volumes / volume.variants を再帰で全部。
    ★variants/versions を落とすと『消えた』偽陽性が出る([[release_date_change_side_effects]])。"""
    def walk_vols(vols, ed):
        for v in vols or []:
            if isinstance(v, dict):
                yield v, ed
                for sub in ("variants", "versions"):
                    for vv in v.get(sub) or []:
                        if isinstance(vv, dict):
                            yield vv, ed
    for ed in page.get("editions") or []:
        if not isinstance(ed, dict):
            continue
        yield from walk_vols(ed.get("volumes"), ed)
        for ver in ed.get("versions") or []:
            if isinstance(ver, dict):
                yield from walk_vols(ver.get("volumes"), ed)


def scan_production(since: str):
    """isbn13 → 巻レコード(複数頁に在ることもある)"""
    by_isbn = defaultdict(list)
    n_pages = n_vols = 0
    for f in sorted(glob.glob(os.path.join(SRC, "*.yml"))):
        try:
            with io.open(f, encoding="utf-8") as fh:
                page = yaml.load(fh, Loader=_YL) or {}
        except Exception:
            continue
        if not isinstance(page, dict):
            continue
        n_pages += 1
        stem = os.path.basename(f)[:-4]
        pub_slug = page.get("slug") or stem
        for v, ed in iter_volumes(page):
            isbn = norm_isbn(v.get("isbn13"))
            if len(isbn) != 13:
                continue
            n_vols += 1
            rd = str(v.get("release_date") or "")
            by_isbn[isbn].append({
                "stem": stem, "pub_slug": pub_slug,
                "title": page.get("title") or "", "status": page.get("status") or "",
                "year_started": page.get("year_started"), "year_ended": page.get("year_ended"),
                "number": v.get("number"), "release_date": rd,
                "cover_url": v.get("cover_url") or "",
                "etype": ed.get("type") or "", "imprint": ed.get("imprint") or "",
            })
    return by_isbn, n_pages, n_vols


# ---------------- 楽天側の証拠 ----------------

def load_harvest():
    ev = {}
    for path in (HARVEST_PREV, HARVEST):   # 新しい方を後に読んで上書き
        if not os.path.exists(path):
            continue
        stamp = date.fromtimestamp(os.path.getmtime(path)).isoformat()
        for ln in io.open(path, encoding="utf-8"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            isbn = norm_isbn(d.get("isbn"))
            if len(isbn) != 13:
                continue
            iso, prec = parse_sales(d.get("salesDate"))
            ev[isbn] = {"iso": iso, "prec": prec, "raw": d.get("salesDate") or "",
                        "title": d.get("title") or "", "cover": d.get("cover") or "",
                        "src": "harvest", "at": stamp,
                        "unknown": bool(d.get("unknown_date"))}
    return ev


def live_lookup(isbns, limit):
    """ハーベストに無い分を楽天 live で。 ★_lookup の共通ヘルパ経由(429/backoff/レートを一本化)。"""
    import importlib
    LK = importlib.import_module("_lookup")
    env = LK._env()
    cache = {}
    if os.path.exists(LIVE_CACHE):
        try:
            cache = json.load(io.open(LIVE_CACHE, encoding="utf-8"))
        except Exception:
            cache = {}
    todo = [i for i in isbns if i not in cache][:limit]
    print("[live] todo=%d (cached=%d)" % (len(todo), len(cache)), file=sys.stderr)
    for n, isbn in enumerate(todo, 1):
        items = LK.rakuten_live_retry(env, isbn=isbn) or []
        it = (items[0].get("Item", items[0]) if items else None)
        if it:
            iso, prec = parse_sales(it.get("salesDate"))
            cache[isbn] = {"iso": iso, "prec": prec, "raw": it.get("salesDate") or "",
                           "title": it.get("title") or "", "cover": it.get("largeImageUrl") or "",
                           "src": "live", "at": date.today().isoformat(), "unknown": False,
                           "availability": it.get("availability") or ""}
        else:
            cache[isbn] = {"iso": None, "prec": "none", "raw": "", "title": "", "cover": "",
                           "src": "live-empty", "at": date.today().isoformat(), "unknown": False}
        if n % 25 == 0:
            json.dump(cache, io.open(LIVE_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            print("  live %d/%d" % (n, len(todo)), file=sys.stderr)
    json.dump(cache, io.open(LIVE_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return cache


# ---------------- 層の判定 ----------------

def build_layers():
    pre = {os.path.basename(f)[:-4] for f in glob.glob(os.path.join(PREORDER_DIR, "*.yml"))}
    canon = {os.path.basename(f)[:-4] for f in glob.glob(os.path.join(CANON_DIR, "*.yml"))}
    seed4 = set()
    for name in ("volumes-supplement.yml", "volumes-supplement-auto.yml"):
        p = os.path.join(ROOT, "data", "seeds", name)
        if not os.path.exists(p):
            continue
        try:
            y = yaml.load(io.open(p, encoding="utf-8"), Loader=_YL) or {}
        except Exception:
            continue
        for v in (y.get("volumes") or []):
            if isinstance(v, dict) and v.get("isbn13"):
                seed4.add(norm_isbn(v["isbn13"]))
    ovr_keys = set()
    p = os.path.join(ROOT, "data", "seeds", "edition-overrides.json")
    if os.path.exists(p):
        try:
            ovr_keys = set(json.load(io.open(p, encoding="utf-8")).keys())
        except Exception:
            pass
    have_ovr = set()
    p = os.path.join(ROOT, "data", "seeds", "release-date-override.jsonl")
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("isbn13"):
                have_ovr.add(norm_isbn(d["isbn13"]))
    return pre, canon, seed4, ovr_keys, have_ovr


def fix_layer(rec, isbn, pre, canon, seed4, ovr_keys):
    if isbn in seed4:
        return "SEED4"
    if rec["stem"] in canon:
        return "CANONICAL"
    if rec["pub_slug"] in ovr_keys or rec["stem"] in ovr_keys:
        return "OVERRIDES"
    if rec["stem"] in pre:
        return "PREORDER"
    return "SEED2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=(date.today() - timedelta(days=120)).isoformat(),
                    help="この日以降の発売日を持つ巻だけ見る(既定=今日-120日)")
    ap.add_argument("--minor-days", type=int, default=3,
                    help="この日数以内のズレは MINOR(奥付 vs 店頭)として別枠")
    ap.add_argument("--live", action="store_true", help="ハーベストに無い未発売巻を楽天liveで確認")
    ap.add_argument("--limit", type=int, default=400, help="--live の1回の上限")
    a = ap.parse_args()

    today = date.today().isoformat()
    print("[1/4] 本番走査 ...", file=sys.stderr)
    prod, n_pages, n_vols = scan_production(a.since)
    print("      頁 %d / 巻(ISBN付) %d / ユニークISBN %d" % (n_pages, n_vols, len(prod)), file=sys.stderr)

    print("[2/4] 楽天ハーベスト読み込み ...", file=sys.stderr)
    ev = load_harvest()
    print("      証拠 %d 件 (%s)" % (len(ev), HARVEST), file=sys.stderr)

    # 対象 = 「本番の日付が since 以降」 or 「楽天の日付が since 以降」 の ISBN
    targets = set()
    for isbn, recs in prod.items():
        if any(r["release_date"] and r["release_date"][:10] >= a.since for r in recs):
            targets.add(isbn)
    for isbn, e in ev.items():
        if isbn in prod and e["iso"] and e["iso"][:10] >= a.since:
            targets.add(isbn)
    print("      対象ISBN %d" % len(targets), file=sys.stderr)

    live = {}
    if a.live:
        need = sorted(i for i in targets
                      if i not in ev
                      and any((r["release_date"] or "") >= today for r in prod[i]))
        print("[3/4] live 対象(未発売なのに楽天ハーベスト不在) %d" % len(need), file=sys.stderr)
        live = live_lookup(need, a.limit)
    else:
        print("[3/4] live skip (--live で有効化)", file=sys.stderr)
        if os.path.exists(LIVE_CACHE):
            try:
                live = json.load(io.open(LIVE_CACHE, encoding="utf-8"))
            except Exception:
                live = {}

    pre, canon, seed4, ovr_keys, have_ovr = build_layers()

    print("[4/4] 突合 ...", file=sys.stderr)
    rows = []
    cls = Counter()
    for isbn in sorted(targets):
        e = ev.get(isbn) or live.get(isbn)
        for rec in prod[isbn]:
            ours = rec["release_date"]
            if not e:
                if ours and ours >= today:
                    klass, theirs, prec, src, at = "NOT_LISTED", "", "", "", ""
                else:
                    continue
            elif e.get("src") == "live-empty":
                klass, theirs, prec, src, at = "NOT_LISTED", "", "", e["src"], e["at"]
            elif not e.get("iso") or e.get("unknown"):
                klass, theirs, prec, src, at = "NO_DATE", e.get("raw") or "", e.get("prec") or "", e["src"], e["at"]
            else:
                theirs, prec, src, at = e["iso"], e["prec"], e["src"], e["at"]
                if prec not in ("day", "day~"):
                    # 年/年月しか無い = 比較できない(頁の日付の方が精密なら触らない)
                    if ours[:len(theirs)] == theirs:
                        continue
                    klass = "NO_DATE"
                elif not ours:
                    klass = "OURS_EMPTY"
                elif ours == theirs:
                    continue
                else:
                    d = days_between(ours, theirs)
                    if d is None:
                        klass = "NO_DATE"
                    elif abs(d) <= a.minor_days:
                        klass = "MINOR"
                    elif d > 0:
                        klass = "POSTPONED"
                    else:
                        klass = "ADVANCED"
            delta = days_between(ours, theirs) if (ours and theirs and len(theirs) == 10) else ""
            layer = fix_layer(rec, isbn, pre, canon, seed4, ovr_keys)
            unreleased = "yes" if (theirs and len(theirs) == 10 and theirs >= today) or \
                                  (ours and ours >= today) else "no"
            placeholder = "yes" if re.search(r"/\d{13}\.gif", rec["cover_url"] or "") else "no"
            cls[klass] += 1
            rows.append([
                klass, layer, rec["stem"], rec["pub_slug"], isbn,
                str(rec["number"] if rec["number"] is not None else ""),
                ours, theirs, str(delta), prec, src, at,
                "yes" if isbn in have_ovr else "no", unreleased, placeholder,
                rec["status"], rec["etype"], rec["imprint"],
                str(len(prod[isbn])), rec["title"], (e or {}).get("title", ""),
            ])

    hdr = ["class", "fix_layer", "stem", "pub_slug", "isbn13", "vol",
           "ours", "theirs", "delta_days", "prec", "ev_src", "ev_at",
           "has_override", "unreleased", "placeholder_cover",
           "page_status", "edition_type", "imprint", "n_pages_with_isbn",
           "page_title", "rakuten_title"]
    order = {"POSTPONED": 0, "ADVANCED": 1, "NOT_LISTED": 2, "OURS_EMPTY": 3, "MINOR": 4, "NO_DATE": 5}
    rows.sort(key=lambda r: (order.get(r[0], 9), r[7] or "", r[2]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(hdr) + "\n")
        for r in rows:
            fh.write("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in r) + "\n")

    print("\n=== 発売日ドリフト監査 (%s) ===" % today)
    for k in sorted(cls, key=lambda k: order.get(k, 9)):
        print("  %-11s %5d" % (k, cls[k]))
    core = [r for r in rows if r[0] in ("POSTPONED", "ADVANCED") and r[13] == "yes"]
    print("  --- 芯(未発売 かつ 日付が動いた) %d ---" % len(core))
    lc = Counter(r[1] for r in core)
    for k, v in lc.most_common():
        print("      %-10s %d" % (k, v))
    print("\n出力: %s" % OUT)


if __name__ == "__main__":
    main()
