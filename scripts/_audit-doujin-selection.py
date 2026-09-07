# -*- coding: utf-8 -*-
"""【型・検出器】同人セレクション/同人作家コレクションが本番に載っている層(2026-09-07 新設)。

★ユーザ発見: 頁「ハル」(hal-ayase) の唯一の巻 9784865893540 は
  楽天 seriesName = **「POE BACKS 同人作家コレクション 268」** = 同人誌の商業セレクション。
  CLAUDE.md の掲載対象外(drop imprint patterns に '同人')に該当するのに載っていた。
  ★レーベル(imprint)は「Poe backs」で、同じレーベルには商業BL(Baby comics 等)も居るので
  **レーベル名では判別できない**。 判別できるのは楽天の seriesName。

判定 = 本番頁に載っているISBNのうち、楽天ローカル種の seriesName / title / subTitle に
  「同人」を含むもの。 ★「同人誌」「同人作家」「同人アンソロジー」等を拾う。
  ★除外語 = 「同人誌即売会」を題材にした**商業漫画**(げんしけん型)を巻き込まないよう、
  seriesName に出た時だけ強い信号とし、title/sub だけの一致は弱い信号として分けて出す。

出力: docs/production-diagnostics/doujin-selection.tsv
使用: python scripts/_audit-doujin-selection.py
"""
import os
import sys
import json
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    pi = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    prod = set(pi.keys())
    print("本番に載っているISBN {:,}".format(len(prod)), flush=True)

    hits = []
    n = 0
    for isbn, it in R.iter_items((R.DELTA, R.OLD)):
        n += 1
        if n % 200000 == 0:
            print("  ...{:,} item 走査".format(n), flush=True)
        if isbn not in prod:
            continue
        ser = R.clean_title(it.get("seriesName", ""))
        title = R.clean_title(it.get("title", ""))
        sub = R.clean_title(it.get("subTitle", ""))
        if "同人" not in (ser + title + sub):
            continue
        hits.append({
            "isbn": isbn, "tier": "SERIES" if "同人" in ser else "TITLE",
            "pages": pi.get(isbn) if isinstance(pi.get(isbn), list) else [pi.get(isbn)],
            "series": ser, "title": title, "sub": sub,
            "publisher": it.get("publisherName", ""), "author": R.clean_title(it.get("author", "")),
            "salesDate": it.get("salesDate", ""),
        })
    print("走査 {:,} item / 「同人」を含む本番掲載本 {}".format(n, len(hits)), flush=True)

    bypage = defaultdict(list)
    for h in hits:
        for s in (h["pages"] or []):
            if s:
                bypage[s].append(h)
    cols = ["tier", "slug", "isbn", "series", "title", "sub", "publisher", "author", "salesDate",
            "page_vols_hit"]
    dst = os.path.join(ROOT, "docs", "production-diagnostics", "doujin-selection.tsv")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for slug in sorted(bypage):
            for h in sorted(bypage[slug], key=lambda x: x["isbn"]):
                f.write("\t".join([h["tier"], slug, h["isbn"], h["series"], h["title"], h["sub"],
                                   h["publisher"], h["author"], h["salesDate"],
                                   str(len(bypage[slug]))]) + "\n")
    ns = len({s for s in bypage})
    nser = len({s for s in bypage if any(h["tier"] == "SERIES" for h in bypage[s])})
    print("該当頁 {} (うち seriesName一致 = 強い信号 {}) → {}".format(ns, nser, dst))


if __name__ == "__main__":
    main()
