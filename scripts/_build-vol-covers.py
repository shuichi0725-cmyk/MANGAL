#!/usr/bin/env python3
"""本棚の「番号タイルを押すと書影」用の巻ごとの書影索引 → <out>/vc/NN.json(64分割)。

2026-10-04 ユーザ裁定(本棚: 番号タイル→段の下に前後の書影を覗かせる[3D]→押すと頁のように大きく[P2])。
一覧索引は1巻の書影しか持たないので、作品ごとの巻の書影を別に持つ。 全件1本だと本番で約11MBになるため、
公開slugのハッシュ(FNV-1a 32bit を 64 で割った余り)で64本に分け、本棚は開いた作品の1本だけ読む
(★ハッシュは lib/volCovers.ts の vcShard と必ず同じ)。

中身 = {公開slug: [[巻番号, 書影(楽天は接頭辞を落とした短縮形), 発売日], ...]}。
巻 = その作品で整数の巻番号が最も多い版(=一覧索引の max_edition_volumes と同じ数え方)の巻。
使い方: python scripts/_build-vol-covers.py <mangaDir> <outDir>
  テスト環境: preview CI が .preview-data/manga → public で作る(git には入れない)。
  ★本番はまだ配線していない(本棚がテスト環境専用のため)。 本番化する時は週次の索引生成と r2-sync に足す。
"""
import glob, json, os, re, sys

import yaml

try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
SHARDS = 64
_RK_PRE = "https://thumbnail.image.rakuten.co.jp/@0_mall/"


def fnv1a(s: str) -> int:
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def slim(c):
    """一覧索引の slim_cover と同じ規則(楽天の接頭辞と ?_ex を落とす。 想定外のクエリはそのまま)。"""
    if not c or not c.startswith(_RK_PRE):
        return c or None
    rest = re.sub(r"\?_ex=\d+x\d+$", "", c[len(_RK_PRE):])
    return c if "?" in rest else rest


def int_vols(vs):
    return [v for v in vs or [] if isinstance(v.get("number"), int)]


def main():
    src, out = sys.argv[1], sys.argv[2]
    shards = [dict() for _ in range(SHARDS)]
    n_works = n_vols = 0
    for fp in glob.glob(os.path.join(src, "*.yml")):
        d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        if not isinstance(d, dict) or not d.get("slug"):
            continue
        best = None
        for e in d.get("editions") or []:
            vs = int_vols(e.get("volumes"))
            if best is None or len(vs) > len(best):
                best = vs
        if not best:
            continue
        seen, rows = set(), []
        for v in sorted(best, key=lambda x: x["number"]):
            if v["number"] in seen:
                continue
            seen.add(v["number"])
            rows.append([v["number"], slim(v.get("cover_url")), v.get("release_date")])
        slug = str(d["slug"])
        shards[fnv1a(slug) % SHARDS][slug] = rows
        n_works += 1
        n_vols += len(rows)
    od = os.path.join(out, "vc")
    os.makedirs(od, exist_ok=True)
    size = 0
    for i, sh in enumerate(shards):
        p = os.path.join(od, f"{i:02d}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(sh, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        size += os.path.getsize(p)
    print(f"巻の書影索引: {n_works}作 / {n_vols}巻 → {od} ({SHARDS}本・計 {size/1e6:.2f}MB)")


if __name__ == "__main__":
    main()
