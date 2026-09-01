# -*- coding: utf-8 -*-
"""外部エンリッチの作業行を展開 (= skill external-enrich の Step2)。

バックログTSV(= _enrich-backlog-scan.py の出力)の N行目〜M行目について、
SRC stem / 公開slug / 既存catch-syn / 巻数 / レーベル / ジャンル を1行にまとめて出す。
★末尾に PUBS=<公開slug,...> を出す = そのまま _enrich-captions.py --slugs に渡せる
  (_enrich-captions.py は **公開slug** で照合する。SRC stem を渡すと無言で素通りする)。

usage:
  WL_TSV=docs/production-diagnostics/enrich-backlog-5vol-pre2010.tsv \
    python scripts/_enrich-worklist.py 1 18
"""
import io
import os
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
TSV = os.environ.get("WL_TSV", "docs/production-diagnostics/enrich-backlog-5vol-2010.tsv")
a, b = int(sys.argv[1]), int(sys.argv[2])

rows = [l.rstrip("\n").split("\t") for l in io.open(TSV, encoding="utf-8")][1:]
pubs = []
for i in range(a - 1, min(b, len(rows))):
    r = rows[i]
    stem = r[3]
    p = "data/manga.v2/%s.yml" % stem
    if not os.path.exists(p):
        print("%3d %-44s [頁なし=drop済]" % (i + 1, stem))
        continue
    d = yaml.safe_load(io.open(p, encoding="utf-8"))
    c = (d.get("catch") or "").strip()
    y = (d.get("synopsis") or "").strip()
    if c and y:
        print("%3d %-44s [済]" % (i + 1, stem))
        continue
    pubs.append(d.get("slug") or stem)
    print("%3d stem=%s pub=%s | %s | %s | %s巻 | %s-%s | %s | genres=%s" % (
        i + 1, stem, d.get("slug"), d.get("title"),
        "/".join(x["name"] for x in (d.get("authors") or [])),
        r[2], d.get("year_started"), d.get("year_ended"),
        (d.get("editions") or [{}])[0].get("imprint"), d.get("genres")))
    print("     catch=%s" % (c[:60] or "(空)"))
    print("     syn  =%s" % (y[:90] or "(空)"))
print("PUBS=" + ",".join(pubs))
