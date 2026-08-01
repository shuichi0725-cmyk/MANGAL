#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""検索スナップショット試験の固定コーパスを作る(lib/__fixtures__/search-corpus.json)。

★なぜ固定コーパスなのか
  実索引 data/manga-list-index.json は週次で中身が増減するため、そのままスナップショットを
  取ると「データが変わった」だけで試験が赤くなり、コード起因の退行と区別できない。
  そこで実索引から★決定的に★抜いた固定コーパスを git に置き、これを土台にする。
  → 差分が出た = コードが挙動を変えた、と言い切れる。

★決定性(同じ実索引からは必ず同じ結果)
  - slug の辞書順で全体を並べ、等間隔サンプリング(乱数を使わない)
  - 過去に事故が起きた作品(PIN_SLUGS)は必ず含める
  - cover 列は落とす(検索/絞り込み/並べ替えのどれも参照しないのにサイズの大半を占める)

使い方:
  python scripts/_build-search-fixture.py            # 既定 2500 件
  python scripts/_build-search-fixture.py --n 4000
"""
import argparse
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga-list-index.json")
ALT_SRC = os.path.join(ROOT, "data", "manga-alt-index.json")
OUT_DIR = os.path.join(ROOT, "lib", "__fixtures__")
OUT = os.path.join(OUT_DIR, "search-corpus.json")
OUT_ALT = os.path.join(OUT_DIR, "search-corpus-alt.json")

# ★過去の退行事故の当事者+検索の代表例。ここが抜けると事故の再発を検知できない。
PIN_SLUGS = [
    "one-piece", "kimetsu-no-yaiba", "shingeki-no-kyojin", "naruto", "berserk",
    "ranma-2-bunnoichi", "nanatsu-no-taizai", "faibu-star-stories",
    "rosario-to-vampire", "rosario-to-vampire-season-2",
    "golgo-13", "oishinbo", "tsuribaka-nisshi", "cooking-papa", "meitantei-conan",
    "patalliro", "shizukanaru-don", "yowamushi-pedal", "tenpai", "onihei-hankachou",
    # 代表クエリが 0件 にならないように実体を入れておく(0件のクエリは番人にならない)
    "gegege-no-kitarou", "hakaba-kitarou", "jojo-no-kimyou-na-bouken-stone-ocean", "jojorion",
    "kochira-katsushikaku-kameari-kouen-mae-hashutsujo",
]

DROP_FIELDS = {"cover"}  # 検索・絞り込み・並べ替えのいずれも参照しない=コーパスから外す


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2500, help="コーパス件数(既定2500)")
    a = ap.parse_args()

    if not os.path.exists(SRC):
        print(f"★abort: {SRC} が無い。先に _build-list-index.py で索引を作る。")
        return 2

    raw = json.load(io.open(SRC, encoding="utf-8"))
    fields = raw["f"]
    rows = raw["d"]
    si = fields.index("slug")

    keep_idx = [i for i, f in enumerate(fields) if f not in DROP_FIELDS]
    keep_fields = [fields[i] for i in keep_idx]

    by_slug = {r[si]: r for r in rows}
    ordered = sorted(rows, key=lambda r: r[si] or "")

    picked: dict[str, list] = {}
    for s in PIN_SLUGS:
        r = by_slug.get(s)
        if r is not None:
            picked[s] = r
    missing = [s for s in PIN_SLUGS if s not in picked]

    # 残り枠を等間隔サンプリングで埋める(決定的)
    room = max(0, a.n - len(picked))
    if room and ordered:
        step = max(1, len(ordered) // room)
        for i in range(0, len(ordered), step):
            r = ordered[i]
            if len(picked) >= a.n:
                break
            picked.setdefault(r[si], r)

    out_rows = [[r[i] for i in keep_idx] for r in sorted(picked.values(), key=lambda r: r[si] or "")]
    os.makedirs(OUT_DIR, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump({"f": keep_fields, "d": out_rows}, f, ensure_ascii=False, separators=(",", ":"))

    # alt(別名)もコーパスぶんだけ切り出す
    slugs = {r[0] for r in out_rows} if keep_fields[0] == "slug" else set(picked.keys())
    alt_n = 0
    if os.path.exists(ALT_SRC):
        alt = json.load(io.open(ALT_SRC, encoding="utf-8"))
        sub = {k: v for k, v in alt.items() if k in slugs}
        alt_n = len(sub)
        with io.open(OUT_ALT, "w", encoding="utf-8") as f:
            json.dump(sub, f, ensure_ascii=False, separators=(",", ":"))

    print(f"コーパス {len(out_rows)}件 / 列 {len(keep_fields)}(cover除外) → {os.path.relpath(OUT, ROOT)}"
          f" {os.path.getsize(OUT)//1024}KB")
    print(f"alt {alt_n}件 → {os.path.relpath(OUT_ALT, ROOT)} {os.path.getsize(OUT_ALT)//1024 if alt_n else 0}KB")
    if missing:
        print(f"★注意: PIN_SLUGS のうち索引に見つからなかった slug = {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
