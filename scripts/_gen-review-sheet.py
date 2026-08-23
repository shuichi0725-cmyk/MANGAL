# -*- coding: utf-8 -*-
"""previewレビューシート生成 (2026-08-24 ユーザGO①)。

新規頁/日次ドラフトを「書影+題+slug+著者+出版社+レーベル+ジャンル」の1行に並べたHTMLを吐く。
1頁ずつ開かず一覧で異常(書影欠け/出版社unknown/slug異常/コンビニ風レーベル/ジャンル空)を見つけるための道具。
異常セルは色付け。日次蒸留・頁化のたびに生成してユーザに渡す。

usage:
  python scripts/_gen-review-sheet.py                     # src=.preview-data/manga → .cache/review-sheet.html
  python scripts/_gen-review-sheet.py --src <dir> --out <html>
"""
import argparse
import glob
import html
import io
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW_BASE = "https://mangal-preview.pages.dev/manga/"
KONBINI_HINT = re.compile(r"セレクション|My First Big|リミックス|プラチナコミックス|Gコミックス|廉価|コンビニ|傑作|総集編|蔵出し")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, ".preview-data", "manga"))
    ap.add_argument("--slugs-file", default=None,
                    help="1行1slug(SRC stem)のリスト。指定時は data/manga.v2 からその頁だけを載せる")
    ap.add_argument("--out", default=os.path.join(ROOT, ".cache", "review-sheet.html"))
    a = ap.parse_args()

    if a.slugs_file:
        stems = [s.strip() for s in io.open(a.slugs_file, encoding="utf-8") if s.strip()]
        files = [os.path.join(ROOT, "data", "manga.v2", s + ".yml") for s in stems]
        files = [f for f in files if os.path.exists(f)]
    else:
        files = sorted(glob.glob(os.path.join(a.src, "*.yml")))

    rows = []
    for f in files:
        y = yaml.safe_load(io.open(f, encoding="utf-8")) or {}
        slug = str(y.get("slug") or os.path.basename(f)[:-4])
        vols, cover, dates, imprints = 0, "", [], set()
        for ed in y.get("editions") or []:
            if ed.get("imprint"):
                imprints.add(str(ed["imprint"]))
            for v in ed.get("volumes") or []:
                vols += 1
                if not cover and v.get("cover_url"):
                    cover = str(v["cover_url"])
                if v.get("release_date"):
                    dates.append(str(v["release_date"]))
        pub = y.get("publisher") or "(unknown)"
        authors = "、".join(str(x.get("name")) for x in (y.get("authors") or []))
        genres = " ".join(y.get("genres") or [])
        maxrun = max((len(x) for x in slug.split("-")), default=0)
        flags = []
        if not cover:
            flags.append("書影なし")
        if pub == "(unknown)":
            flags.append("出版社不明")
        if maxrun >= 15 or len(slug) >= 78:
            flags.append("slug異常")
        if not genres:
            flags.append("ジャンル空")
        if not y.get("demographic"):
            flags.append("分野空")
        imp = " / ".join(sorted(imprints))
        if KONBINI_HINT.search(str(y.get("title") or "") + imp):
            flags.append("再録疑い?")
        rows.append({
            "slug": slug, "title": str(y.get("title") or ""), "kana": str(y.get("title_kana") or ""),
            "cover": cover, "authors": authors, "pub": str(pub), "imp": imp,
            "genres": genres, "demo": str(y.get("demographic") or ""), "vols": vols,
            "dates": (min(dates)[:10] + "〜" + max(dates)[:10]) if dates else "", "flags": flags,
        })

    n_flag = sum(1 for r in rows if r["flags"])
    parts = ["""<!doctype html><meta charset="utf-8"><title>MANGAL レビューシート</title>
<style>
body{font-family:sans-serif;font-size:13px;margin:12px;background:#fafafa}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ddd;padding:4px 6px;vertical-align:top;text-align:left}
th{background:#333;color:#fff;position:sticky;top:0}
img{width:60px;height:auto;display:block}
.f{background:#fff3cd}.bad{color:#b00;font-weight:bold}
.slug{font-family:monospace;font-size:11px;word-break:break-all;color:#555}
tr:nth-child(even){background:#f2f2f2}
</style>"""]
    parts.append(f"<h3>レビューシート: {len(rows)}頁 / 要注意 {n_flag}頁</h3>")
    parts.append("<table><tr><th>書影</th><th>題 / slug</th><th>著者</th><th>出版社 / レーベル</th>"
                 "<th>分野 / ジャンル</th><th>巻</th><th>発売日</th><th>フラグ</th></tr>")
    for r in sorted(rows, key=lambda r: (not r["flags"], r["slug"])):
        cls = ' class="f"' if r["flags"] else ""
        img = f'<img src="{html.escape(r["cover"])}" loading="lazy">' if r["cover"] else "—"
        parts.append(
            f"<tr{cls}><td>{img}</td>"
            f'<td><a href="{PREVIEW_BASE}{html.escape(r["slug"])}">{html.escape(r["title"])}</a>'
            f'<div class="slug">{html.escape(r["slug"])}</div>'
            f'<div class="slug">{html.escape(r["kana"])}</div></td>'
            f"<td>{html.escape(r['authors'])}</td>"
            f"<td>{html.escape(r['pub'])}<br>{html.escape(r['imp'])}</td>"
            f"<td>{html.escape(r['demo'])}<br>{html.escape(r['genres'])}</td>"
            f"<td>{r['vols']}</td><td>{html.escape(r['dates'])}</td>"
            f'<td class="bad">{html.escape("、".join(r["flags"]))}</td></tr>')
    parts.append("</table>")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    io.open(a.out, "w", encoding="utf-8", newline="\n").write("\n".join(parts))
    print(f"レビューシート: {len(rows)}頁(要注意{n_flag}) → {a.out}")


if __name__ == "__main__":
    main()
