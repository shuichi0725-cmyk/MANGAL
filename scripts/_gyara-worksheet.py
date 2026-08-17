# -*- coding: utf-8 -*-
"""ギャラ型(巻×発売日の大逆行)の作業台帳を作る。

`_audit-vol-date-regression.py` が吐いた
docs/production-diagnostics/vol-date-regression.tsv から
指定した逆行年数の帯だけを抜き、各頁について
  - 本番頁の版タブ構成(どのタブに何巻・どの日付が入っているか)
  - 種2(db-v2)のクラスタ構成(sid × edition × imprint × 冊数 × 日付レンジ)
を1行にまとめて出す。canonical seed を書く前の下調べを1コマンドにするためのもの。

使い方:
  python scripts/_gyara-worksheet.py --min 20 --max 29
  python scripts/_gyara-worksheet.py --min 20 --max 29 --out docs/production-diagnostics/gyara-worksheet-20s.tsv
"""
import argparse
import io
import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / "docs" / "production-diagnostics" / "vol-date-regression.tsv"
SRC = ROOT / "data" / "manga.v2"
DB = ROOT / ".cache" / "db-v2.sqlite"
CANON = ROOT / "data" / "seeds" / "edition-canonical"


def page_shape(slug):
    p = SRC / (slug + ".yml")
    if not p.exists():
        return "(本番yml無し)"
    try:
        with p.open(encoding="utf-8") as f:
            d = yaml.safe_load(f)
    except Exception as ex:
        return "(yml読めず: %s)" % str(ex)[:60]
    out = []
    for e in d.get("editions") or []:
        vs = e.get("volumes") or []
        ds = [v.get("release_date") for v in vs if v.get("release_date")]
        out.append("%s[%s]%s %d冊 %s〜%s" % (
            e.get("type"), e.get("label"), ("/" + (e.get("imprint") or "-")),
            len(vs), (min(ds) if ds else "-"), (max(ds) if ds else "-")))
    return " ; ".join(out)


def cluster_shape(cur, slug):
    """本番頁のISBN群から種2 sid を逆引きし、その sid の edition 構成を返す。"""
    p = SRC / (slug + ".yml")
    isbns = []
    if p.exists():
        try:
            with p.open(encoding="utf-8") as f:
                d = yaml.safe_load(f)
            for e in d.get("editions") or []:
                for v in e.get("volumes") or []:
                    if v.get("isbn13"):
                        isbns.append(v["isbn13"])
        except Exception:
            pass
    sids = set()
    for i in isbns[:60]:
        for r in cur.execute(
                "SELECT e.series_id FROM volumes v JOIN editions e ON e.id=v.edition_id "
                "WHERE v.isbn13=?", (i,)):
            sids.add(r[0])
    # ★ISBN経由だけだと、ISBNを持たない古いrunが別sidに居る場合に取りこぼす
    #   (エースをねらえ!で実踏)。題でも必ず引いて和を取る。
    title = None
    if p.exists():
        try:
            with p.open(encoding="utf-8") as f:
                title = (yaml.safe_load(f) or {}).get("title")
        except Exception:
            pass
    if title:
        for r in cur.execute("SELECT id FROM series WHERE title=?", (title,)):
            sids.add(r[0])
    out = []
    for sid in sorted(sids):
        # ★同じcursorを内側でも使うと外側のイテレーションが1行で止まる(sqlite3のcursor再利用)。
        #   必ず fetchall() で materialize してから回す。
        eds = cur.execute("SELECT * FROM editions WHERE series_id=?", (sid,)).fetchall()
        for e in eds:
            vs = cur.execute(
                "SELECT number,isbn13,release_date FROM volumes WHERE edition_id=?",
                (e["id"],)).fetchall()
            if not vs:
                continue
            ds = sorted(x["release_date"] for x in vs if x["release_date"])
            out.append("sid%s/ed%s %s[%s] %d冊 %s〜%s ISBN%d" % (
                sid, e["id"], e["type"], e["imprint"] or "-", len(vs),
                ds[0] if ds else "-", ds[-1] if ds else "-",
                sum(1 for x in vs if x["isbn13"])))
    return " || ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=20)
    ap.add_argument("--max", type=int, default=29)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = [l.rstrip("\n").split("\t") for l in TSV.open(encoding="utf-8")]
    head, rows = rows[0], rows[1:]
    hit = [r for r in rows if a.min <= int(r[0]) <= a.max]
    # 頁単位に畳む(同じ頁で複数タブが flag されることがある)
    by_slug = {}
    for r in hit:
        by_slug.setdefault(r[1], []).append(r)

    done = {p.stem for p in CANON.glob("*.yml")}
    db = sqlite3.connect(str(DB))
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    out = a.out or ("docs/production-diagnostics/gyara-worksheet-%d-%d.tsv" % (a.min, a.max))
    f = io.open(ROOT / out, "w", encoding="utf-8", newline="\n")
    f.write("\t".join(["slug", "title", "authors", "canonical済", "worst",
                       "page_shape", "cluster_shape"]) + "\n")
    for slug in sorted(by_slug):
        rs = by_slug[slug]
        worst = " / ".join("%s年 %s %s" % (r[0], r[4], r[6]) for r in rs)
        f.write("\t".join([slug, rs[0][2], rs[0][3], "済" if slug in done else "",
                           worst, page_shape(slug), cluster_shape(cur, slug)]) + "\n")
    f.close()
    print("%d頁 (%d版) → %s" % (len(by_slug), len(hit), out))


if __name__ == "__main__":
    main()
