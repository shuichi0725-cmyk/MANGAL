#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""頁内書影重複の検出器 (= 関東平野型の署名 2026-07-13)。

署名: 同一頁の複数の巻(版・刷・variants横断)に**同じcover_url**が割り当てられている。
真の原因の型: Kobo一括補完の同巻数ゲートが「汚染で巻数が偶然一致した版」を通し、
別版の装丁が複数枠に貼られる(関東平野=道草文庫②③が上中下版の中/下にも貼られた)。
正当な例外がありうるため出力は報告のみ(自動修正しない)。

使い方:
  python scripts/_audit-cover-dup.py               # 全DB掃引
  python scripts/_audit-cover-dup.py --slugs a,b   # 指定頁のみ
出力: docs/production-diagnostics/cover-dup.tsv (slug/題/重複URL/該当巻リスト)
"""
import argparse, glob, os, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
import yaml

try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "cover-dup.tsv")


def norm_url(u):
    """サイズパラメータ差(_ex=200x200 vs 300x300)を吸収して同一画像判定"""
    return str(u or "").split("?")[0]


def scan_page(path):
    slug = os.path.basename(path)[:-4]
    try:
        d = yaml.load(open(path, encoding="utf-8"), Loader=L)
    except Exception:
        return None
    if not d:
        return None
    by_url = defaultdict(list)
    for e in d.get("editions") or []:
        label = e.get("label") or e.get("type")
        # ★versionsがある版は edition.volumes が versions[0] のミラー(後方互換)なので
        #   versions側だけ数える(二重カウント=偽陽性の型。adolf canonical頁で発覚)
        if e.get("versions"):
            pools = [(f"/{ver.get('label')}", ver.get("volumes") or []) for ver in e["versions"]]
        else:
            pools = [("", e.get("volumes") or [])]
        for suffix, vols in pools:
            for v in vols:
                u = norm_url(v.get("cover_url"))
                if u:
                    by_url[u].append(f"{label}{suffix} v{v.get('number')}({v.get('isbn13')})")
                for var in v.get("variants") or []:
                    u2 = norm_url(var.get("cover_url"))
                    if u2:
                        by_url[u2].append(f"{label}{suffix} v{v.get('number')}variant({var.get('isbn13')})")
    dups = {u: hits for u, hits in by_url.items() if len(hits) > 1}
    if not dups:
        return None
    return (slug, d.get("title"), dups)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", help="カンマ区切りで限定")
    a = ap.parse_args()
    if a.slugs:
        paths = [os.path.join(ROOT, "data", "manga.v2", f"{s}.yml") for s in a.slugs.split(",")]
    else:
        paths = glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))
    hits = []
    for p in paths:
        r = scan_page(p)
        if r:
            hits.append(r)
    hits.sort(key=lambda x: -sum(len(v) for v in x[2].values()))
    with open(OUT, "w", encoding="utf-8") as f:
        for slug, title, dups in hits:
            for u, where in dups.items():
                f.write(f"{slug}\t{title}\t{len(where)}\t{u}\t{' | '.join(where)}\n")
    print(f"頁内書影重複: {len(hits)}頁 → {os.path.relpath(OUT, ROOT)}")
    for slug, title, dups in hits[:20]:
        print(f"  {slug} | {title} | {sum(len(v) for v in dups.values())}巻が重複画像")


if __name__ == "__main__":
    main()
