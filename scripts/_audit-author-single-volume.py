#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""頁の著者欄に居るが、★その頁のたった1冊の書誌にしか現れない★著者を検出する(解説者混入型)。

★なぜ要るか (= 2026-08-07 ユーザ発見『メトロポリス』から型化)
  手塚治虫『メトロポリス』の著者欄に★藤子不二雄Ⓐ★が入っていた。出所を追うと、
  4版のうち**角川文庫版(9784041851203)のMADB creator にだけ**「藤子不二雄A」が居た。
  文庫の**解説を書いた漫画家**が creator に流れ込む型で、他3版・楽天著者・JPRO出版権は
  いずれも手塚治虫のみだった。

★既存 _audit-author-not-in-volumes.py との違い
  あちらは「どの巻の書誌にも**一度も**現れない」(=作品と無関係な著者)を見る。
  こちらは「**現れはするが1冊だけ**」を見る。解説者/寄稿者は実際に奥付に載るので
  あちらの網には掛からない。★手塚治虫漫画全集・文庫版・愛蔵版のように
  他の漫画家が解説を寄せる慣習のある版で効く。

判定(全部を満たす時だけ出す。単著の作品で誤爆しないための条件):
  - その頁の巻のうち、MADB creator を引けた巻が **3冊以上**
  - 対象著者が現れるのは **1冊だけ**
  - 同じ頁に **8割以上の巻に現れる著者**が別に居る(=主著者が明確)
  - 対象著者が現れるその1冊にも、主著者が同居している(=主著者を置換した別作品ではない)

出力: docs/production-diagnostics/author-single-volume.tsv
使い方:
  python scripts/_audit-author-single-volume.py
  python scripts/_audit-author-single-volume.py --only metropolis
"""
import argparse
import collections
import glob
import io
import json
import os
import re
import sys
import unicodedata

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
META = os.path.join(ROOT, ".cache", "madb", "metadata101-clean.json")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "author-single-volume.tsv")


def norm_name(s: str) -> str:
    """照合キー。★丸囲みA(藤子不二雄Ⓐ)とA(藤子不二雄A)を同一視する
    (MADBは素のA・本番は丸囲み。これを揃えないと同一人物が別人に割れる)。
    空白/中黒無視は [[author_name_space_conventions_conflict]] と同じ規則。"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.replace("Ⓐ", "A").replace("Ⓑ", "B").replace("ⓐ", "a")
    return re.sub(r"[\s　・,、/]", "", s).lower()


def to13(i: str) -> str:
    i = re.sub(r"[^0-9Xx]", "", str(i or ""))
    if len(i) == 13:
        return i
    if len(i) == 10:
        c = i[:9]
        s = sum((3 if k % 2 else 1) * int(d) for k, d in enumerate("978" + c))
        return "978" + c + str((10 - s % 10) % 10)
    return ""


def load_isbn_creators(needed: set) -> dict:
    """isbn13 → MADB schema:creator の名前集合。★楽天ではなく種1を使う。
    楽天の author は代表者しか出さないことがあり、「1冊にだけ居る」を判定できない。"""
    out = {}
    if not os.path.exists(META):
        print(f"! {META} が無い", file=sys.stderr)
        return out
    g = json.load(io.open(META, encoding="utf-8"))
    rows = g.get("@graph", g) if isinstance(g, dict) else g
    for r in rows:
        i = r.get("schema:isbn") or r.get("isbn")
        if isinstance(i, list):
            i = i[0] if i else None
        k = to13(i)
        if not k or k not in needed:
            continue
        cr = r.get("schema:creator")
        names = [cr] if isinstance(cr, str) else [x for x in (cr or []) if isinstance(x, str)]
        s = {norm_name(x) for x in names if norm_name(x)}
        if s:
            out[k] = s
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
        aus = [x.get("name") for x in (d.get("authors") or []) if isinstance(x, dict) and x.get("name")]
        if len(aus) < 2:
            continue                     # 単著は対象外(比較相手が居ない)
        isbns = []
        for e in (d.get("editions") or []):
            for v in (e.get("volumes") or []):
                k = to13(v.get("isbn13"))
                if k:
                    isbns.append(k)
        if len(set(isbns)) < 3:
            continue                     # 3冊未満は多数決が立たない
        pages.append((os.path.basename(p)[:-4], d.get("title"), aus, sorted(set(isbns))))
        need.update(isbns)
    print(f"候補 {len(pages)} 頁 / ISBN {len(need)}", flush=True)

    cre = load_isbn_creators(need)
    print(f"種1で creator を引けた ISBN {len(cre)}", flush=True)

    rows = []
    for slug, title, aus, isbns in pages:
        have = [i for i in isbns if i in cre]
        if len(have) < 3:
            continue
        cnt = collections.Counter()
        for i in have:
            for nm in cre[i]:
                cnt[nm] += 1
        tot = len(have)
        main_names = {nm for nm, c in cnt.items() if c >= tot * 0.8}
        if not main_names:
            continue
        for au in aus:
            k = norm_name(au)
            if k in main_names:
                continue
            if cnt.get(k, 0) != 1:
                continue
            src = [i for i in have if k in cre[i]][0]
            if not (cre[src] & main_names):
                continue                 # その1冊に主著者が居ない=別作品の混入(既存監査の領域)
            rows.append((slug, title, au, tot, src, "/".join(sorted(main_names)), "/".join(aus)))

    # ★アンソロジー除け(2026-08-07): 巻ごとに執筆者が違う本(りぼん新人まんが家デビュー作集型)は
    #   「1冊にだけ居る著者」が構造的に大量に出る=正当。1頁から3人以上出たらそちら側に寄せる。
    per_page = collections.Counter(r[0] for r in rows)
    out_rows = [(("アンソロジー疑い" if per_page[r[0]] >= 3 else "解説者疑い"),) + r for r in rows]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("判定\tslug\t題\t疑い著者\t書誌を引けた冊数\t出所ISBN(この1冊だけ)\t主著者\t頁の著者欄\n")
        for r in sorted(out_rows):
            f.write("\t".join(str(x) for x in r) + "\n")
    c = collections.Counter(r[0] for r in out_rows)
    print(f"検出 {len(out_rows)} 件 {dict(c)} → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
