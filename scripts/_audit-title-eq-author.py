#!/usr/bin/env python3
"""月次監査: title==著者名 の壊れレコード検出。

MADBクラスタリングで実タイトル/副題が脱落し series.title が著者名に化けたページを flag。
kana も著者読みになり誤る (= 「夜明け」型)。 蒸留で再発しうるので月次で機械検出する。

出力: docs/production-diagnostics/title-eq-author.tsv (slug / title / kana / nvol / isbn)
使い方: python scripts/_audit-title-eq-author.py [data/manga.v2]
"""
import glob, os, sys, yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "manga.v2")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "title-eq-author.tsv")

def main():
    hits = []
    n = 0
    for p in glob.glob(os.path.join(SRC, "*.yml")):
        n += 1
        try:
            d = yaml.safe_load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        t = (d.get("title") or "").strip()
        auth = [(a.get("name") or "").strip() for a in (d.get("authors") or [])]
        if t and t in auth:
            eds = d.get("editions") or []
            nvol = sum(len(e.get("volumes") or []) for e in eds)
            isbn = next((v.get("isbn13") for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")), "")
            hits.append((os.path.basename(p)[:-4], t, d.get("title_kana") or "", nvol, isbn))
    hits.sort(key=lambda h: -h[3])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("slug\ttitle\ttitle_kana\tnvol\tisbn\n")
        for s, t, k, nv, ib in hits:
            f.write(f"{s}\t{t}\t{k}\t{nv}\t{ib}\n")
    print(f"スキャン {n} / title==著者名 {len(hits)}件 → {OUT}", file=sys.stderr)
    print(f"  ★該当は実タイトル/副題脱落の疑い(NDL by-ISBNで実題確認 → title/kana是正 or 抜粋本drop)", file=sys.stderr)

if __name__ == "__main__":
    main()
