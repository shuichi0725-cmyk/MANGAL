#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★年サフィックス二重頁層 (= ハンター×ハンター型 2026-07-28 ユーザ発見で型化)。

同名slug衝突の解決規則(-姓+西暦 suffix)は「真の同名別作品」用だが、実際には
**同一作品の別クラスタ**(MADB別ID再登録 / 表記揺れ分裂 / 頁化やり直しの残骸)にも
機械適用され、本番に二重頁を作っていた(07-28実測: 同著者229組中165組がISBN交差)。

検出 = 本番一覧索引で「slug末尾が[-姓]西暦」×「基底slugも本番に実在」×「同著者」を拾い、
manga.v2 の ISBN交差と源頁の _skey で3分類:
  REDO_LEFTOVER  = 同一_skey(頁化やり直しで旧slug版が残った残骸) → 機械削除可
  CLUSTER_SPLIT  = _skey相違+ISBN交差(MADB別ID再登録/表記揺れ分裂)   → per-case統合
  NO_OVERLAP     = ISBN交差ゼロ(外伝/第2部/〇〇編=概ね正当な別頁)     → 報告のみ
  FILE_MISSING   = slug名のファイルがmanga.v2に無い=★夜明け型(ファイル名≠slug)が大半。
                   幽霊と即断せずgrepで実体を逆引きして手動裁定(2026-07-28: 3件とも実体あり。
                   私立極道高校2011=題に年が入った正当別作/湘南グラフティ・トロッキー=交差0の分裂疑い)
出力 = docs/production-diagnostics/year-suffix-dup.tsv
入口側ゲート = _torikoboshi-genpages.py(同_skey既出skip+同著者衝突hold 2026-07-28)。
月次サニティ: 取込後に走らせ、REDO_LEFTOVER/CLUSTER_SPLIT の新規増加=ゲートすり抜けsignal。
"""
import json
import os
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_TSV = os.path.join(ROOT, "docs", "production-diagnostics", "year-suffix-dup.tsv")
PAT = re.compile(r"^(.*?)-(?:[a-z]+)?((?:19|20)\d{2})$")
SRC_DIRS = ("data/seeds/source-pages", "data/manga", "data/seeds/preorder-pages")


def isbns(slug: str):
    p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
    if not os.path.exists(p):
        return None
    d = yaml.safe_load(open(p, encoding="utf-8"))
    out = set()
    for e in d.get("editions") or []:
        for v in e.get("volumes") or []:
            if v.get("isbn13"):
                out.add(str(v["isbn13"]))
        for ver in e.get("versions") or []:
            for v in ver.get("volumes") or []:
                if v.get("isbn13"):
                    out.add(str(v["isbn13"]))
    return out


def skey(slug: str):
    for d in SRC_DIRS:
        p = os.path.join(ROOT, d, slug + ".yml")
        if os.path.exists(p):
            m = re.search(r"^_skey:\s*(.+)$", open(p, encoding="utf-8", errors="replace").read(4000), re.M)
            if m:
                return m.group(1).strip()
    return None


def main() -> int:
    idx = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = idx["f"]
    SI, TI, AI = f.index("slug"), f.index("title"), f.index("authors")
    by_slug = {str(r[SI]): r for r in idx["d"]}

    def akey(v):
        return re.sub(r"[\s　]", "", str(v or ""))

    rows = []
    for slug, r in by_slug.items():
        m = PAT.match(slug)
        if not m:
            continue
        base = m.group(1)
        b = by_slug.get(base)
        if b is None:
            continue
        if not akey(r[AI]) or akey(r[AI]) != akey(b[AI]):
            continue  # 別著者 = 正当な同名別作品(中華一番型)は対象外
        ia, ib = isbns(slug), isbns(base)
        ov = -1 if (ia is None or ib is None) else len(ia & ib)
        if ov > 0:
            ks, kb = skey(slug), skey(base)
            cls = "REDO_LEFTOVER" if (ks and kb and ks == kb) else "CLUSTER_SPLIT"
        elif ov == 0:
            cls = "NO_OVERLAP"
        else:
            cls = "FILE_MISSING"
        rows.append((cls, slug, base, str(r[TI]), str(b[TI]), ov,
                     len(ia or []), len(ib or [])))

    order = {"CLUSTER_SPLIT": 0, "REDO_LEFTOVER": 1, "FILE_MISSING": 2, "NO_OVERLAP": 3}
    rows.sort(key=lambda x: (order[x[0]], -x[5]))
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, "w", encoding="utf-8", newline="") as fp:
        fp.write("class\tslug\tbase\ttitle\tbase_title\tisbn_overlap\tn_slug\tn_base\n")
        for row in rows:
            fp.write("\t".join(str(x) for x in row) + "\n")

    from collections import Counter
    c = Counter(r[0] for r in rows)
    print(f"年サフィックス×同著者: {len(rows)}組 → {dict(c)}")
    print(f"  CLUSTER_SPLIT = per-case統合worklist / REDO_LEFTOVER = 機械削除可(要GO) / NO_OVERLAP = 概ね正当")
    print(f"  → {os.path.relpath(OUT_TSV, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
