#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""頁の著者欄に居るのに、★その頁のどの巻の書誌にも現れない★著者を検出する。

★なぜ要るか (= 2026-08-02 ユーザ発見『よろしくメカドック』から型化)
  よろしくメカドック(次原隆二)の著者欄に★秋本治★が入っていた。秋本治の紐付き先は
  他が全て「こち亀」関連で、この1作だけが浮いていた。
  種2 の series_authors に居るが、種1(MADB metadata101)の巻別 schema:creator には
  一度も現れない = 作品と何の関係も無い著者。

★なぜ他の signal では駄目だったか(実測)
  - series_key の qid と著者 qid の不一致 → 8,625件。大半が★正当な原作+作画★
    (武論尊 qid × 池上遼一 artist 等)。
  - さらに「両方 writer_artist」で絞る → 4,784件。それでも 武論尊×原哲夫(北斗の拳)、
    アンソロジー(花とゆめプラチナ)、原作小説家(阿刀田高/橋田壽賀子/デュマ・フィス)等が大半。
  → 役割データが粗い([[author_roles_state]] 101-cleanが役割を剥がした)ため、
    ★巻の書誌に実際に載っているか★という一次情報で判定するのが唯一確実。

出力: docs/production-diagnostics/author-not-in-volumes.tsv
使い方:
  python scripts/_audit-author-not-in-volumes.py
  python scripts/_audit-author-not-in-volumes.py --only yoroshiku-mechadoc
"""
import argparse
import collections
import glob
import io
import os
import json
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
RAKUTEN = [os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"),
           os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")]
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "author-not-in-volumes.tsv")

def norm_name(s: str) -> str:
    """著者名の照合キー。★空白/中黒は無視する(MADB無空白 vs 楽天の空白入りが別人に割れる
    実害の吸収。[[author_name_space_conventions_conflict]] と同じ規則)。"""
    return re.sub(r"[\s　・,、/]", "", s or "")


def build_isbn_authors(needed: set) -> dict:
    """isbn13 → 著者名集合(楽天 author)。
    ★当初は種1(MADB metadata101)で突合しようとしたが、古い書籍は種1に無く
    (よろしくメカドックのジャンプ・コミックス12巻は1件も入っていなかった)判定不能だった。
    楽天は書影取得のために全頁ぶん引いてあるので被覆が広い。"""
    out = {}
    for fn in RAKUTEN:
        if not os.path.exists(fn):
            continue
        for line in io.open(fn, encoding="utf-8", errors="replace"):
            if '"author"' not in line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            i = (o.get("isbn") or "").strip()
            if i not in needed:
                continue
            au = ((o.get("item") or {}).get("author") or "").strip()
            if au:
                # 楽天は「原作:A/作画:B」「A,B」等で連名。区切って全部入れる
                for nm in re.split(r"[,、/／・]| ", au):
                    nm = norm_name(nm)
                    if nm:
                        out.setdefault(i, set()).add(nm)
                out.setdefault(i, set()).add(norm_name(au))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="slug をカンマ区切りで指定(調査用)")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(SRC, "*.yml")))
    if a.only:
        want = set(a.only.split(","))
        files = [p for p in files if os.path.basename(p)[:-4] in want]
    print(f"走査 {len(files)} 頁", flush=True)

    pages, need = [], set()
    for n, p in enumerate(files, 1):
        if n % 20000 == 0:
            print(f"  読込 {n}", flush=True)
        try:
            d = yaml.safe_load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        au = [x.get("name") for x in (d.get("authors") or []) if x.get("name")]
        oau = [x.get("name") for x in (d.get("original_authors") or []) if x.get("name")]
        if len(au) + len(oau) < 2:
            continue  # 単独著者は比較する意味が無い(混入は複数人の時だけ)
        isbns = [str(v.get("isbn13")) for e in (d.get("editions") or [])
                 for v in (e.get("volumes") or []) if v.get("isbn13")]
        if not isbns:
            continue
        pages.append((d.get("slug") or os.path.basename(p)[:-4], d.get("title") or "", au, oau, isbns))
        need.update(isbns)
    print(f"  複数著者の頁 {len(pages)} / 照合ISBN {len(need):,} → 楽天を走査", flush=True)

    icr = build_isbn_authors(need)
    print(f"  楽天で著者が取れたISBN: {len(icr):,}", flush=True)

    rows = []
    for slug, title, au, oau, isbns in pages:
        found = set()
        cover = 0
        for i in isbns:
            if i in icr:
                cover += 1
                found |= icr[i]
        if cover == 0:
            continue  # 楽天に1巻も無い頁は判定不能
        for nm in au + oau:
            if norm_name(nm) not in found:
                rows.append([slug, title, nm, str(len(isbns)), str(cover),
                             " / ".join(sorted(found))[:70]])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # ★reason列(2026-08-20 gyara-anomalies方式): 裁定済み行の「なぜ触らない/何をした」を
    #   末尾列に持ち、再実行しても消えない(旧TSVから slug+著者名 キーで引き継ぐ)。
    #   空 = 未裁定。書式は docs/production-diagnostics/README.md を参照。
    old_reason = {}
    if os.path.exists(OUT):
        with io.open(OUT, encoding="utf-8") as fh:
            head = fh.readline().rstrip("\n").split("\t")
            if "reason" in head:
                i_sl, i_au, i_rs = head.index("slug"), head.index("巻書誌に無い著者"), head.index("reason")
                for line in fh:
                    c = line.rstrip("\n").split("\t")
                    if len(c) > i_rs and c[i_rs]:
                        old_reason[(c[i_sl], c[i_au])] = c[i_rs]
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(["slug", "題", "巻書誌に無い著者", "頁の巻数",
                            "照合できた巻数", "巻書誌にある著者", "reason"]) + "\n")
        for r in sorted(rows):
            fh.write("\t".join(r) + "\t" + old_reason.get((r[0], r[2]), "") + "\n")
    print(f"\n★巻の書誌に一度も現れない著者 = {len(rows)}件 / {len({r[0] for r in rows})}頁"
          f" → {os.path.relpath(OUT, ROOT)}")
    print("★自動削除しない。原作者・企画・別名義は巻書誌に載らないことがある(要人手裁定)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
