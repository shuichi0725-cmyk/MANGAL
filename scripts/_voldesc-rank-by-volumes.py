#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巻説明の対象slugを **未生成巻数の多い順** に並べたリストを出す(2026-07-31 ユーザ指示)。

★従来の既定は「ファイル名順=端から全件」([[feedback_no_popularity_priority]] の人気順禁止方針)。
  今回は**人気順ではなく巻数順**への切替。1作の材料収集で得られる巻数が変わるため歩留まりに直結する。

対象巻の数え方は `_voldesc-material.py` の target_volumes() と同じ規約に揃える:
  - 主版(type=standard のうち最古発売。standard皆無なら全版から最古)の巻だけ
  - 同じ巻番号がどこかの版/刷で seed 済みなら完了扱いで数えない
  - 材料なし確定(no-material.txt)の ISBN は数えない

usage:
  python scripts/_voldesc-rank-by-volumes.py > .cache/voldesc/rank.txt     # 全件(多い順)
  python scripts/_voldesc-rank-by-volumes.py --top 40                      # 上位40作だけ
  python scripts/_voldesc-rank-by-volumes.py --min 10                      # 未生成10巻以上の作だけ
"""
import json, io, os, sys, glob, argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import yaml
try:
    from yaml import CSafeLoader as Loader
except ImportError:
    from yaml import SafeLoader as Loader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--src", default=os.path.join(ROOT, "data", "manga.v2"))
ap.add_argument("--top", type=int, default=0)
ap.add_argument("--min", type=int, default=1, help="未生成巻数がこれ未満の作は出さない")
ap.add_argument("--stats", action="store_true", help="件数の分布だけ出す")
a = ap.parse_args()

# seed 済 ISBN
seed_only = set()
sp = os.path.join(ROOT, "data", "seeds", "volume-desc-ja.jsonl")
if os.path.exists(sp):
    for l in io.open(sp, encoding="utf-8"):
        try:
            seed_only.add(json.loads(l).get("isbn13"))
        except Exception:
            pass
# 材料なし確定
done = set()
np_ = os.path.join(ROOT, ".cache", "voldesc", "no-material.txt")
if os.path.exists(np_):
    done = {x.strip() for x in io.open(np_, encoding="utf-8") if x.strip()}


def primary_edition(d):
    """主版 = type=standard のうち最古発売。standard皆無なら全版から最古。"""
    eds = [e for e in (d.get("editions") or []) if (e.get("volumes") or [])]
    if not eds:
        return None
    std = [e for e in eds if e.get("type") == "standard"] or eds

    def key(e):
        ds = [str(v.get("release_date") or "9999") for v in (e.get("volumes") or [])]
        return min(ds) if ds else "9999"
    return sorted(std, key=key)[0]


rows = []
for p in sorted(glob.glob(os.path.join(a.src, "*.yml"))):
    try:
        d = yaml.load(io.open(p, encoding="utf-8").read(), Loader=Loader)
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    prim = primary_edition(d)
    if prim is None:
        continue
    # 同巻番号の代替ISBN(他版+全刷)
    alt = {}
    for e in d.get("editions") or []:
        lists = ([] if e is prim else [e.get("volumes")]) + [vv.get("volumes") for vv in (e.get("versions") or [])]
        for vl in lists:
            for v in vl or []:
                ib = str(v.get("isbn13") or "")
                if len(ib) == 13 and v.get("number") is not None:
                    alt.setdefault(v["number"], []).append(ib)
    pvols = prim.get("volumes") or []
    prim_ibs = {str(v.get("isbn13") or "") for v in pvols}
    n = 0
    for v in pvols:
        ib = str(v.get("isbn13") or "")
        if len(ib) != 13:
            continue
        alts = [x for x in alt.get(v.get("number"), []) if x != ib and x not in prim_ibs]
        if ib in seed_only or any(x in seed_only for x in alts):
            continue
        if ib in done:
            continue
        n += 1
    if n >= a.min:
        rows.append((n, os.path.basename(p)[:-4]))

rows.sort(key=lambda x: (-x[0], x[1]))
if a.stats:
    tot = sum(n for n, _ in rows)
    print(f"未生成巻を持つ作品 {len(rows):,} / 未生成巻 合計 {tot:,}", file=sys.stderr)
    for th in (100, 50, 30, 20, 10, 5, 2):
        c = [x for x in rows if x[0] >= th]
        print(f"  {th:>3}巻以上: {len(c):>6,}作 / {sum(n for n,_ in c):>7,}巻", file=sys.stderr)
    sys.exit(0)

out = rows[: a.top] if a.top else rows
for n, s in out:
    print(s)
print(f"出力 {len(out):,}作 / 未生成巻 {sum(n for n, _ in out):,}", file=sys.stderr)
