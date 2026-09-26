"""魔法の書架(実験頁 /lab/magic-shelf)専用の見本データを作る。

入力 = data/manga-list-index.json(読むだけ。既存の索引ファイルは一切変更しない)
出力 = app/lab/magic-shelf/sample-books.json(この頁だけが読む小さなJSON)

抜き出し = 書影のある作品を人気(popularity)順に上位 N 作(既定1,500)。同点は slug 順で固定。
列 = 書架が使う分だけ(書影・題名・ジャンル・年・巻数・完結 + 並び用のヨミ/1巻発売日/人気)。
書影は索引と同じ slim 形のまま持つ(復元は lib/coverSlim.ts fullCover)。

使い方: python scripts/_gen-magic-shelf-sample.py [--n 1500]
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga-list-index.json")
OUT = os.path.join(ROOT, "app", "lab", "magic-shelf", "sample-books.json")

# 出力の列順(= app/lab/magic-shelf/spell.ts の SAMPLE_FIELDS と一致させる)
FIELDS = ["slug", "title", "kana", "cover", "year", "first", "vols", "status", "genres", "pop"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    n = ap.parse_args().n

    with open(SRC, encoding="utf-8") as fh:
        idx = json.load(fh)
    col = {k: i for i, k in enumerate(idx["f"])}
    rows = [r for r in idx["d"] if r[col["cover"]]]
    rows.sort(key=lambda r: (-(r[col["popularity"]] or -1), r[col["slug"]]))
    picked = rows[:n]

    out_rows = [
        [
            r[col["slug"]],
            r[col["title"]],
            r[col["title_kana"]] or "",
            r[col["cover"]],
            r[col["year_started"]] or 0,
            r[col["first_volume_date"]] or "",
            r[col["max_edition_volumes"]] or 0,
            r[col["status"]],
            r[col["genres"]] or [],
            r[col["popularity"]] or 0,
        ]
        for r in picked
    ]
    # 1行1作(git の差分を読めるように)
    body = ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in out_rows)
    head = json.dumps({"src": "data/manga-list-index.json", "n": len(out_rows), "f": FIELDS}, ensure_ascii=False)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head[:-1] + ',"d":[\n' + body + "\n]}\n")
    print(f"書影あり {len(rows):,} 作のうち人気上位 {len(out_rows):,} 作 → {os.path.relpath(OUT, ROOT)}")
    print(f"  人気 {picked[0][col['popularity']]:,} 〜 {picked[-1][col['popularity']]:,} / {os.path.getsize(OUT):,} bytes")


if __name__ == "__main__":
    main()
