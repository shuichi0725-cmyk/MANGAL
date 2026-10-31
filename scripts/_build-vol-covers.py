#!/usr/bin/env python3
"""本棚の「番号タイルを押すと書影」用の巻ごとの書影索引 → <out>/vc/NN.json(64分割)。

2026-10-04 ユーザ裁定(本棚: 番号タイル→段の下に前後の書影を覗かせる[3D]→押すと頁のように大きく[P2])。
一覧索引は1巻の書影しか持たないので、作品ごとの巻の書影を別に持つ。 全件1本だと本番で約11MBになるため、
公開slugのハッシュ(FNV-1a 32bit を 64 で割った余り)で64本に分け、本棚は開いた作品の1本だけ読む
(★ハッシュは lib/volCovers.ts の vcShard と必ず同じ)。

中身 = {公開slug: [[巻番号, 書影(楽天は接頭辞を落とした短縮形), 発売日], ...]}。
巻 = その作品で整数の巻番号が最も多い版(=一覧索引の max_edition_volumes と同じ数え方)の巻。
  ★書影が無い巻は、同じ版の別の刷(versions = 初版カバー/新装版カバー 等)の同じ巻番号の書影と発売日で補う
    (2026-10-31 ユーザ報告=うる星やつら: 版の巻 = 書影0の「初版カバー(1980-87)」で、本棚の番号タイルが34巻とも書影なし。
    作品頁は書影の揃った「新装版カバー(2006-08)」を先に出している)。 巻数が並ぶ版どうしは補った後の書影が多い方。
    ★巻の数え方(どの巻番号が並ぶか)は変えない = 本棚の番号タイル(一覧索引の max_edition_volumes)と揃える。
    (刷を別の版に割る作品頁の数え方にすると、6巻の作品が4巻になる等ずれた = 2026-10-31 実測6作)
  ★版ごと(2026-10-31 本棚 A+1 = 同じ作品の別の版を別々にしまえる): 表示ブロックが2つ以上の作品は、同じ1本の
    "~e" に {公開slug: {版ラベル: 巻}} も持つ。 版ラベル・版の割り方は作品頁の displayBlocks と同じ
    (刷の ISBN が互いに重ならない時は「版ラベル 刷ラベル」で刷ごとに別。 重なる刷は書影だけ補う)。
    旧JS は sh[slug] しか読まないので、同じファイルの別キーなら壊れない。
使い方: python scripts/_build-vol-covers.py <mangaDir> <outDir>
  テスト環境: preview CI が .preview-data/manga → public で作る(git には入れない)。
  本番(2026-10-31 本棚の本番化で配線): 週次 step1 の vol-covers が data/manga.v2 → data で作る(git には入れない)。
    配るのは r2-sync(out/vc を data/vc で上書き)と差分反映(中身が変わった分だけ PUT)。 一覧 = scripts/_index_files.py の VC_FILES。
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


def version_covers(e):
    """その版の別の刷(versions)の書影: 巻番号 → (書影, 発売日)。 刷は古い順に並ぶ = 先に見つかった刷を採る。"""
    out = {}
    for x in e.get("versions") or []:
        if not isinstance(x, dict):
            continue
        for v in int_vols(x.get("volumes")):
            if v.get("cover_url"):
                out.setdefault(v["number"], (v["cover_url"], v.get("release_date")))
    return out


def rows_of(vols, alt):
    """巻 → [[巻番号, 書影, 発売日], ...](番号順・重複番号は先の1冊)。 書影の無い巻は alt(別の刷)の書影+発売日で補う。"""
    seen, rows = set(), []
    for v in sorted(int_vols(vols), key=lambda x: x["number"]):
        if v["number"] in seen:
            continue
        seen.add(v["number"])
        if v.get("cover_url") or v["number"] not in alt:
            rows.append([v["number"], slim(v.get("cover_url")), v.get("release_date")])
        else:  # 書影は別の刷から = 発売日もその刷の物(絵と日付を食い違わせない)
            c, rd = alt[v["number"]]
            rows.append([v["number"], slim(c), rd or v.get("release_date")])
    return rows


def display_blocks(editions):
    """作品頁の表示ブロック(components/VolumeRow.tsx displayBlocks)と同じ割り方と名前 → [(版ラベル, 巻, 補う書影)]。"""
    out = []
    for e in editions or []:
        vers = [x for x in (e.get("versions") or []) if isinstance(x, dict)]
        if len(vers) > 1:
            sets = [{v.get("isbn13") for v in (x.get("volumes") or []) if v.get("isbn13")} for x in vers]
            if all(not (sets[i] & sets[j]) for i in range(len(sets)) for j in range(len(sets)) if i != j):
                out.extend((f"{e.get('label')} {x.get('label')}", x.get("volumes") or [], {}) for x in vers)
                continue
        out.append((str(e.get("label")), e.get("volumes") or [], version_covers(e)))
    return out


def main():
    src, out = sys.argv[1], sys.argv[2]
    shards = [dict() for _ in range(SHARDS)]
    n_works = n_vols = n_multi = 0
    for fp in glob.glob(os.path.join(src, "*.yml")):
        d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        if not isinstance(d, dict) or not d.get("slug"):
            continue
        best, best_key, alt = None, None, {}
        for e in d.get("editions") or []:
            vs = int_vols(e.get("volumes"))
            vc = version_covers(e)
            key = (len(vs), sum(1 for v in vs if v.get("cover_url") or v["number"] in vc))  # 巻数 → 補った後の書影の数
            if best is None or key > best_key:
                best, best_key, alt = vs, key, vc
        if not best:
            continue
        rows = rows_of(best, alt)
        slug = str(d["slug"])
        sh = shards[fnv1a(slug) % SHARDS]
        sh[slug] = rows
        n_works += 1
        n_vols += len(rows)
        # 版ごと(表示ブロックが2つ以上の作品だけ)。 同じ名前の版が2つあれば先の版(作品頁の「しまう」も名前で引く)
        eds = {}
        for label, vols, valt in display_blocks(d.get("editions")):
            r = rows_of(vols, valt)
            if r:
                eds.setdefault(label, r)
        if len(eds) > 1:
            sh.setdefault("~e", {})[slug] = eds
            n_multi += 1
    od = os.path.join(out, "vc")
    os.makedirs(od, exist_ok=True)
    size = 0
    for i, sh in enumerate(shards):
        p = os.path.join(od, f"{i:02d}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(sh, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        size += os.path.getsize(p)
    print(f"巻の書影索引: {n_works}作 / {n_vols}巻 / 版ごと {n_multi}作 → {od} ({SHARDS}本・計 {size/1e6:.2f}MB)")


if __name__ == "__main__":
    main()
