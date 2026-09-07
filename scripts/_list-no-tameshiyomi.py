#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""試し読み未取得の「現役・巻数多め」作品リスト (2026-09-07 ユーザ依頼で新設)

条件(既定):
  ①最終巻の発売月が --since 以降(既定 2025-01)= 現役/直近まで刊行が続いている
  ②巻数が --min-vols 以上(既定 5)   ★巻数 = **版内最大**(max_edition_volumes)。
    total_volumes は全版の合計なので、3巻×4版=12 のように多版作を水増しする。
  ③`data/tameshiyomi-map.json` に slug が無い = 試し読みリンクが1本も無い

入力は索引2本だけ(66k頁の生走査をしない)= 数秒。
出力: docs/production-diagnostics/no-tameshiyomi-active.tsv (+ --csv で .csv も)
      巻数の多い順。

usage: python scripts/_list-no-tameshiyomi.py [--since 2025-01] [--min-vols 5] [--csv]
       [--exclude-unreleased]   # 最新巻が未発売(予約)の作品を除く
"""
import argparse, csv, datetime, io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "no-tameshiyomi-active")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-01", help="最終巻発売月の下限 YYYY-MM")
    ap.add_argument("--min-vols", type=int, default=5)
    ap.add_argument("--csv", action="store_true", help="TSVに加えCSVも出す(Excel用にBOM付き)")
    ap.add_argument("--exclude-unreleased", action="store_true",
                    help="最新巻がまだ発売日を迎えていない(予約)作品を除く")
    a = ap.parse_args()

    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    tame = set(json.load(io.open(os.path.join(ROOT, "data", "tameshiyomi-map.json"), encoding="utf-8")))
    this_month = datetime.date.today().strftime("%Y-%m")

    def g(r, k):
        i = F.get(k)
        return r[i] if i is not None and i < len(r) else None

    rows = []
    for r in idx["d"]:
        latest = g(r, "latest_date") or ""
        vols = g(r, "max_edition_volumes") or 0
        slug = g(r, "slug")
        if latest < a.since or vols < a.min_vols or slug in tame:
            continue
        if a.exclude_unreleased and latest > this_month:
            continue
        # authors は "name\tkana" パック(索引圧縮)。名前だけ取り出す。
        au = [str(x).split("\t")[0] for x in (g(r, "authors") or [])]
        oau = [str(x).split("\t")[0] for x in (g(r, "original_authors") or [])]
        rows.append({
            "巻数": vols,
            "タイトル": g(r, "title"),
            "最新巻発売月": latest,
            "未発売": "予約" if latest > this_month else "",
            "状態": g(r, "status") or "",
            "著者": "/".join(oau + au),
            "出版社": g(r, "publisher") or "",
            "総巻数(全版合計)": g(r, "total_volumes") or 0,
            "slug": slug,
            "URL": f"https://mangal.shuichi0725.workers.dev/manga/{slug}",
        })
    rows.sort(key=lambda x: (-x["巻数"], x["タイトル"] or ""))
    cols = list(rows[0].keys()) if rows else ["巻数", "タイトル"]

    with io.open(OUT + ".tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for x in rows:
            f.write("\t".join(str(x[c]).replace("\t", " ") for c in cols) + "\n")
    print(f"{len(rows)} 件 → {OUT}.tsv")
    if a.csv:
        # ★Excel が UTF-8 と判るよう BOM 付き。題の , や \" は csv モジュールが正しく quote する。
        with io.open(OUT + ".csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} 件 → {OUT}.csv")
    print(f"条件: 最終巻 >= {a.since} / 巻数(版内最大) >= {a.min_vols} / 試し読み無し"
          + (" / 未発売除外" if a.exclude_unreleased else ""))


if __name__ == "__main__":
    main()
