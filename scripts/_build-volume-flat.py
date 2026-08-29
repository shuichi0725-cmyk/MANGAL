# -*- coding: utf-8 -*-
"""本番 manga.v2 を **巻1行のフラットTSV** に展開する (2026-08-29 新設)。

矛盾監査(ISBN/発売日など)を書くたびに 69,000 個の yml を舐め直すのは無駄なので、
親が1回だけ展開して中間成果を配る。検出器はこの1ファイルだけを読めばよい。

出力: .cache/volume-flat.tsv (TSV・ヘッダ付き)
  slug, title, status, year_started, year_ended, publisher_key, magazine,
  ed_idx, ed_type, ed_label, ed_imprint, ed_publisher,
  number, volume_label, isbn13, release_date, has_cover, has_desc, is_version
★is_version=1 は versions[](刷タブ)由来の巻。主 volumes は 0。

  python scripts/_build-volume-flat.py
"""
import glob, io, os, sys
import yaml
try:
    from yaml import CSafeLoader as L
except Exception:
    from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
COLS = ["slug", "title", "status", "year_started", "year_ended", "publisher_key", "magazine",
        "ed_idx", "ed_type", "ed_label", "ed_imprint", "ed_publisher",
        "number", "volume_label", "isbn13", "release_date", "has_cover", "has_desc", "is_version"]


def cell(x):
    s = "" if x is None else str(x)
    return s.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    npage = nvol = 0
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(COLS) + "\n")
        for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
            try:
                d = yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
            except Exception:
                continue
            npage += 1
            base = [os.path.basename(p)[:-4], d.get("title"), d.get("status"),
                    d.get("year_started"), d.get("year_ended"), d.get("publisher"), d.get("magazine")]
            for ei, e in enumerate(d.get("editions") or []):
                edc = [ei, e.get("type"), e.get("label"), e.get("imprint"), e.get("publisher")]
                groups = [(e.get("volumes") or [], 0)]
                for vv in (e.get("versions") or []):
                    groups.append((vv.get("volumes") or [], 1))
                for vols, isver in groups:
                    for v in vols:
                        nvol += 1
                        f.write("\t".join(cell(x) for x in (base + edc + [
                            v.get("number"), v.get("volume_label"), v.get("isbn13"),
                            v.get("release_date"),
                            1 if v.get("cover_url") else 0,
                            1 if v.get("description") else 0, isver])) + "\n")
            if npage % 10000 == 0:
                print("..%d頁 %d巻" % (npage, nvol), flush=True)
    print("展開完了: %d頁 / %d巻 → %s (%.1fMB)"
          % (npage, nvol, os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
