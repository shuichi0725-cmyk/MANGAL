# -*- coding: utf-8 -*-
"""数字表記揺れによる同一作品の頁分裂検出(READ-ONLY・月次サニティ)。

型見本(2026-07-27 ユーザ発見):
  - ロザリオとバンパイア seasonⅡ(1-12) vs season2(13-14) = ローマ数字vs算用で別クラスタ
  - 初夜(1巻) vs 初夜2(単巻) = 題末尾数字が続巻(全2巻の2巻)だった型
署名A: 同著者 × numnorm(題)一致 の複数頁 → SPLIT(巻相補=統合候補)/DUP(巻交差=汚染疑い)
署名B: numnorm(題)= 他頁のnumnorm(題)+数字N の単巻頁(同著者) → 続巻分裂疑い(報告のみ。
  マンガ家さんとアシスタントさんと2=真の続編全1巻、のような正当例があるため自動統合禁止)
出力: docs/production-diagnostics/numeral-variant-split.tsv
"""
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
import yaml

try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _title_numnorm import numnorm  # noqa: E402

OUT = os.path.join(ROOT, "docs", "production-diagnostics", "numeral-variant-split.tsv")


def akey(authors):
    return "|".join(sorted(re.sub(r"[\s　]", "", a.get("name") or "") for a in (authors or [])))


def main():
    pages = []
    for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        try:
            d = yaml.load(open(f, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not isinstance(d, dict) or not d.get("slug"):
            continue
        nums = sorted({v.get("number") for e in (d.get("editions") or [])
                       for v in (e.get("volumes") or []) if isinstance(v.get("number"), int)})
        pages.append({"slug": d["slug"], "title": d.get("title") or "",
                      "nt": numnorm(d.get("title")), "ak": akey(d.get("authors")),
                      "nums": nums})
    rows = []
    # 署名A: 正規化題+著者一致
    by = {}
    for p in pages:
        if p["nt"] and p["ak"]:
            by.setdefault((p["nt"], p["ak"]), []).append(p)
    for (nt, ak), grp in by.items():
        if len(grp) < 2:
            continue
        allnums = [set(p["nums"]) for p in grp]
        inter = set.intersection(*allnums) if all(allnums) else set()
        cls = "DUP" if inter else "SPLIT"
        rows.append((cls, " / ".join(p["slug"] for p in grp),
                     " / ".join(p["title"] for p in grp),
                     " / ".join(str(p["nums"][:8]) for p in grp)))
    # 署名B: 親題+数字N の単巻頁
    nt_index = {}
    for p in pages:
        nt_index.setdefault((p["nt"], p["ak"]), []).append(p)
    for p in pages:
        if len(p["nums"]) > 1:
            continue
        m = re.match(r"^(.*?)(\d{1,2})$", p["nt"])
        if not m or not m.group(1):
            continue
        parents = nt_index.get((m.group(1), p["ak"])) or []
        for par in parents:
            if par["slug"] == p["slug"]:
                continue
            rows.append(("SEQ?", f'{p["slug"]} -> {par["slug"]}',
                         f'{p["title"]} -> {par["title"]}',
                         f'子{p["nums"]} 親max={par["nums"][-1] if par["nums"] else "?"}'))
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("class\tslugs\ttitles\tnums\n")
        for r in sorted(rows):
            f.write("\t".join(r) + "\n")
    from collections import Counter
    print(f"走査{len(pages)}頁 → " + " / ".join(f"{k}={v}" for k, v in Counter(r[0] for r in rows).items()))
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
