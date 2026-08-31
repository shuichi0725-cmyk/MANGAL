#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""題名索引ハブ(/titles)のページ分割JSON生成 (= SEO: 66k頁への静的クロール導線 2026-08-31)

★単一ソース原則: 50音分類・頁割りはこのscriptだけが行い、出力 titles-pages.json を
  - app/titles/*(Next静的ルート=描画・generateStaticParams)
  - scripts/_gen-sitemap.py(URL列挙)
  の両方が読む(= TS/Python で分類を二重実装するとURL不一致=404 sitemapの型。それを根絶)。

入出力: data/manga-list-index.json → data/titles-pages.json(本番)
        .preview-data/ 同名 → 同名(preview。索引が無い側はskip)
週次: _weekly-step1.py の list-index の後に走る(索引から導出のため)。
"""
from __future__ import annotations
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_SIZE = 200

# 行の定義(濁音・半濁音は同じ行。ヴ=あ行=/authors の GYO と同じ扱い)
GYO = [
    ("a", "あ行", "アイウエオヴ"),
    ("ka", "か行", "カキクケコガギグゲゴ"),
    ("sa", "さ行", "サシスセソザジズゼゾ"),
    ("ta", "た行", "タチツテトダヂヅデド"),
    ("na", "な行", "ナニヌネノ"),
    ("ha", "は行", "ハヒフヘホバビブベボパピプペポ"),
    ("ma", "ま行", "マミムメモ"),
    ("ya", "や行", "ヤユヨ"),
    ("ra", "ら行", "ラリルレロ"),
    ("wa", "わ行", "ワヰヱヲン"),
    ("other", "英数他", ""),
]
_SMALL = str.maketrans("ァィゥェォャュョッヮヵヶ", "アイウエオヤユヨツワカケ")
_ROW = {ch: key for key, _label, chars in GYO for ch in chars}


def classify(kana: str | None, title: str) -> str:
    s = (kana or title or "").strip()
    if not s:
        return "other"
    c = s[0]
    o = ord(c)
    if 0x3041 <= o <= 0x3096:  # ひらがな→カタカナ
        c = chr(o + 0x60)
    c = c.translate(_SMALL)
    return _ROW.get(c, "other")


def build(idx_path: str) -> dict:
    idx = json.load(open(idx_path, encoding="utf-8"))
    f = idx["f"]
    col = {name: i for i, name in enumerate(f)}
    si, ti, ki = col["slug"], col["title"], col["title_kana"]
    ai, yi, vi = col["authors"], col["year_started"], col["total_volumes"]

    groups: dict[str, list] = {key: [] for key, _l, _c in GYO}
    for r in idx["d"]:
        slug, title, kana = r[si], r[ti], r[ki]
        names = [a.split("\t")[0] for a in (r[ai] or [])]
        authors = "・".join(names[:3]) + ("ほか" if len(names) > 3 else "")
        groups[classify(kana, title)].append(
            [slug, title, kana, authors, r[yi], r[vi]])

    gyo_meta = []
    parts: dict[str, list] = {}
    for key, label, _chars in GYO:
        rows = groups[key]
        rows.sort(key=lambda e: (e[2] or e[1] or "", e[0]))  # かな→slug
        n_pages = max(1, math.ceil(len(rows) / PAGE_SIZE)) if rows else 0
        gyo_meta.append({"key": key, "label": label,
                        "pages": n_pages, "count": len(rows)})
        for p in range(n_pages):
            parts[f"{key}-{p + 1}"] = rows[p * PAGE_SIZE:(p + 1) * PAGE_SIZE]
    return {"page_size": PAGE_SIZE, "gyo": gyo_meta, "parts": parts}


def main() -> None:
    for base in ("data", ".preview-data"):
        idx_path = os.path.join(ROOT, base, "manga-list-index.json")
        if not os.path.exists(idx_path):
            print(f"[titles-pages] {idx_path} 無し → skip")
            continue
        out = build(idx_path)
        out_path = os.path.join(ROOT, base, "titles-pages.json")
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
        total = sum(g["count"] for g in out["gyo"])
        print(f"[titles-pages] {out_path}: {total:,}作品 / {len(out['parts'])}頁 "
              f"({', '.join(f'{g['label']}{g['pages']}' for g in out['gyo'])})")


if __name__ == "__main__":
    main()
