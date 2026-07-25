"""★孤児series監査: 種2(db-v2)に在るのに **元頁が無い** = 永久に本番へ出ないseriesを検出。

背景(2026-07-25 発見): promote は **元頁駆動**(`for ypath in SRC_DIR.glob('*.yml')` =
  data/manga + data/seeds/preorder-pages)であって DB駆動ではない。
  月次蒸留は種2にレコードを足すだけで「新規seriesの元頁を作る」工程が無いため、
  MADB由来の新規シリーズは **元頁がある分(=予約ルートで先に作られた分)しか出ない**。
  1.2.18 実測: 新292 series 中 頁化 85(うち preorder由来75) / 未頁化 207。

判定: ★**本番出力 data/manga.v2 に そのseriesのISBNが1本も出てこない** = 孤児。
  元頁側の title/_skey 一致で見ると merge経路(qid/kana/題ゆれ)を拾えず過大に出るため、
  「実際にサイトに出ているか」という結果基準にする(= 誤検出しない代わりに1回66k走査)。
  ★promote が正当に落とす分(成年/非漫画/画集/雑誌/外国版/題patterns)は除外して報告する
  (= 除外理由は promote 本体から import して二重管理を避ける)。

出力: docs/production-diagnostics/orphan-new-series.tsv (read-only。 本番/種2 不変)
usage: python scripts/_audit-orphan-new-series.py [--since YYYY-MM] [--rebuild]
  --since = その発売日以降の巻を持つseriesに限る(既定=全件)
  --rebuild = 元頁ISBN索引(.cache/srcpage-isbn-index.json)を作り直す
"""
import glob
import importlib.util
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SRC_DIRS = [ROOT / "data" / "manga", ROOT / "data" / "seeds" / "preorder-pages"]
IDX = ROOT / ".cache" / "live-isbn-index.json"
OUT = ROOT / "docs" / "production-diagnostics" / "orphan-new-series.tsv"
ISBN = re.compile(r"97[89]\d{10}")


def _promote():
    """promote 本体を import (= drop条件の単一ソース。 main は走らない)。"""
    spec = importlib.util.spec_from_file_location("promote_v2", ROOT / "scripts" / "_promote-bulk-v2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_index():
    """本番出力 data/manga.v2 に実在する ISBN の集合(= サイトに出ている巻)。"""
    seen = set()
    n = 0
    for p in glob.glob(str(ROOT / "data" / "manga.v2" / "*.yml")):
        n += 1
        if n % 20000 == 0:
            print(f"    ...{n:,}頁", flush=True)
        try:
            seen.update(ISBN.findall(open(p, encoding="utf-8").read()))
        except Exception:
            continue
    print(f"  本番 {n:,}頁 / 掲載ISBN {len(seen):,}", flush=True)
    IDX.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    return seen


def _imprint_dropped(P, imp):
    """promote の imprint drop 条件(= L1216付近と同一)を1つの版について判定。"""
    imp = imp or ""
    imp_l = imp.lower()
    if any(p in imp for p in P.DROP_IMPRINT_PATTERNS):
        return True
    if any(p in imp_l for p in P.DROP_IMPRINT_LOWER_PATTERNS):
        return True
    if "=" not in imp and any(p in imp_l for p in P.DROP_IMPRINT_LOWER_PATTERNS_NO_EQ):
        return True
    return False


def _all_imprints_dropped(P, imps):
    """全版が drop対象 = このseriesは promote が正当に落とす(1版でも残れば孤児候補)。"""
    imps = {i for i in (imps or set())}
    return bool(imps) and all(_imprint_dropped(P, i) for i in imps)


def main():
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]
    if "--rebuild" in sys.argv or not IDX.exists():
        print("[1/3] 本番掲載ISBN索引を構築 ...", flush=True)
        live = build_index()
    else:
        live = set(json.loads(IDX.read_text(encoding="utf-8")))
        print(f"[1/3] 本番掲載ISBN索引(既存) {len(live):,} ★promote後は --rebuild", flush=True)

    print("[2/3] promote の drop条件を読み込み ...", flush=True)
    P = _promote()
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    non_manga = {e["series_key"] for e in
                 (P.yaml.safe_load((ROOT / "data/seeds/non-manga-drop.yml").read_text(encoding="utf-8")) or {})
                 .get("non_manga", []) if isinstance(e, dict) and e.get("series_key")}
    art_books = set(P.load_art_books().keys())
    drop_keys = set(P._load_drop_series_keys() or set())

    # ★分裂クラスタ切り分け: 同題の本番頁が既にある = 作品自体は掲載済み(= 別クラスタに合流済/未合流)
    _ix = json.loads((ROOT / "data" / "manga-list-index.json").read_text(encoding="utf-8"))
    _ti = _ix["f"].index("title")
    live_titles = {r[_ti] for r in _ix["d"]}

    print("[3/3] series を走査 ...", flush=True)
    rows = con.execute(
        "SELECT s.id, s.series_key, s.title, s.subtitle, s.adult_score, s.qid FROM series s").fetchall()
    vols = {}
    for sid, ib, rd in con.execute(
        "SELECT e.series_id, v.isbn13, v.release_date FROM volumes v "
            "JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"):
        vols.setdefault(sid, []).append((ib, rd or ""))
    imprints, edtypes = {}, {}
    for sid, ip, ty in con.execute("SELECT series_id, imprint, type FROM editions"):
        imprints.setdefault(sid, set()).add(ip or "")
        edtypes.setdefault(sid, set()).add(ty or "")
    authors = {}
    for sid, nm in con.execute(
            "SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"):
        authors.setdefault(sid, []).append(nm)

    orphans, reasons = [], {}
    for sid, key, title, sub, adult, qid in rows:
        vv = vols.get(sid) or []
        if not vv:
            continue                                    # ISBN無し = 判定不能(別監査の領域)
        if since and max(rd for _, rd in vv) < since:
            continue
        title = title or ""
        if any(ib in live for ib, _ in vv):
            continue                                    # 1巻でもサイトに出ている = 孤児でない
        why = None
        if (adult or 0) >= 3:
            why = "adult"
        elif key in non_manga:
            why = "non_manga_drop"
        elif key in art_books:
            why = "art_book"
        elif key in drop_keys:
            why = "drop_key"
        elif any(title.startswith(p) for p in P.DROP_TITLE_PREFIX_PATTERNS):
            why = "title_prefix"
        elif any(p in title for p in P.DROP_TITLE_CONTAINS_PATTERNS):
            why = "title_contains"
        elif any(p in (sub or "") for p in P.DROP_SUBTITLE_PATTERNS):
            why = "subtitle"
        elif _all_imprints_dropped(P, imprints.get(sid, set())):
            why = "imprint"          # ★全版がコンビニ本/増刊/bilingual等 = promoteが正当に落とす
        elif edtypes.get(sid) and not (edtypes[sid] & P.KEEP_EDITION_TYPES):
            why = "edition_type"     # ★全版が anime/other/renewal 等 = 掲載対象外の版種
        if why:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        dates = sorted(rd for _, rd in vv if rd)
        orphans.append((key, title, "同題頁あり" if title in live_titles else "未掲載", sub or "", len(vv),
                        dates[0] if dates else "", dates[-1] if dates else "",
                        " / ".join(sorted(imprints.get(sid, set()))[:3]),
                        " / ".join(authors.get(sid, [])[:3]), vv[0][0]))

    orphans.sort(key=lambda r: (r[6], r[1]), reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("series_key\ttitle\tclass\tsubtitle\tvols\tfirst_date\tlast_date\timprints\tauthors\tisbn\n")
        for r in orphans:
            f.write("\t".join(str(x) for x in r) + "\n")

    print(f"\n=== 孤児series (種2に在るが元頁が無い) ===")
    print(f"  ★孤児: {len(orphans):,}   (正当drop除外後)")
    print(f"  正当drop内訳: {reasons}")
    print(f"  → {OUT}")
    from collections import Counter
    print(f"  内訳: 未掲載 {sum(1 for r in orphans if r[2]=='未掲載'):,} / "
          f"同題頁あり(=分裂クラスタ) {sum(1 for r in orphans if r[2]=='同題頁あり'):,}")
    c = Counter(r[6][:4] for r in orphans if r[6] and r[2] == "未掲載")
    print(f"  未掲載の発売年分布(上位): {dict(sorted(c.items(), reverse=True)[:10])}")


if __name__ == "__main__":
    main()
