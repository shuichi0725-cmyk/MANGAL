# -*- coding: utf-8 -*-
"""【保留タスクの再算出器】種2にISBN付きで在るのに本番に1冊も出ていない版を数える(2026-09-07)。

★これは検出器(月次サニティ)ではなく、保留にした是正タスクを再開する時の**下ごしらえ**。
  名前を `_audit-`/`_check-` にしていないのは、登録の番人(_check-sanity-registry.py)の
  対象にしないため(月次で回すものではない)。

背景 = 夕陽よ昇れ!! で発覚。 promote は版タブを **type だけ**で束ねるので、同じ type の別レーベルが
1タブに合流し、巻番号の衝突で負けた版が丸ごと本番に出ない。
既存 `_audit-edition-typemerge-loss.py` は **ISBNから引いた出版社が実際に違う**時だけ挙げる設計
(imprint文字列比較は表記ゆれを誤検出するため)なので、
**同一出版社の別レーベル**(フラワーコミックス vs フラワーコミックスワイド)は対象外。 ここはそれも数える。

★★素の件数は仕事の量ではない([[feedback_raw_count_is_not_worklist]])。
  中身にコンビニ廉価再録(マンサンQコミックス/REKC/HMB/マイファーストビッグ/Akita top comics 等)が
  相当混じっている。 **着手する時はまずレーベルを「正規の別版」と「廉価再録」に分類する**こと。

出力: docs/production-diagnostics/hidden-editions.tsv
使用: python scripts/_scan-hidden-editions.py
"""
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}


def nz(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def promote_drop_patterns():
    """promote の除外レーベル語をソースから読む(二重管理しない)。"""
    src = open(os.path.join(ROOT, "scripts", "_promote-bulk-v2.py"), encoding="utf-8").read()

    def grab(name):
        m = re.search(r"^" + name + r"\s*=\s*(\[.*?\])\s*$", src, re.S | re.M)
        return eval(m.group(1)) if m else []
    return grab("DROP_IMPRINT_PATTERNS"), grab("DROP_IMPRINT_LOWER_PATTERNS")


def main():
    prod = set(json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"),
                              encoding="utf-8")).keys())
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    eds, meta = defaultdict(list), {}
    for sk, eid, etype, imp, isbn in con.execute(
            "SELECT se.series_key, e.id, e.type, e.imprint, v.isbn13 "
            "FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id "
            "WHERE v.isbn13 IS NOT NULL"):
        eds[(sk, eid)].append(nz(isbn))
        meta[(sk, eid)] = (etype, imp or "", sk)

    shown_sk = set()
    for k, isbns in eds.items():
        if set(isbns) & prod:
            shown_sk.add(k[0])

    drop, drop_low = promote_drop_patterns()

    def excluded(etype, imp):
        if etype not in KEEP:
            return True
        if any(p in imp for p in drop):
            return True
        low = imp.lower()
        return any(p in low for p in drop_low)

    rows = []
    for k, isbns in eds.items():
        s = set(isbns)
        if s & prod:
            continue                      # 1冊でも出ていれば対象外
        if k[0] not in shown_sk:
            continue                      # 頁そのものが無い = 別の話
        etype, imp, sk = meta[k]
        rows.append({"n": len(s), "type": etype, "imprint": imp, "series_key": sk,
                     "excluded": "除外レーベル" if excluded(etype, imp) else "",
                     "isbns": ",".join(sorted(s)[:20])})
    rows.sort(key=lambda r: (-r["n"], r["series_key"]))
    cols = ["n", "type", "imprint", "series_key", "excluded", "isbns"]
    dst = os.path.join(ROOT, "docs", "production-diagnostics", "hidden-editions.tsv")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", " ") for c in cols) + "\n")
    real = [r for r in rows if not r["excluded"]]
    print("頁は在るのに1冊も出ていない版: {:,} 版 / {:,} 巻".format(
        len(rows), sum(r["n"] for r in rows)))
    print("  promote の除外レーベル語を当てた残り: {:,} 版 / {:,} 巻".format(
        len(real), sum(r["n"] for r in real)))
    print("  ★この残りにも廉価再録が混じる = **そのまま worklist にしない**。まずレーベル分類。")
    print("  type別:", dict(Counter(r["type"] for r in real).most_common()))
    print("  レーベル上位:", Counter(r["imprint"] for r in real).most_common(12))
    print("→ " + dst)


if __name__ == "__main__":
    main()
