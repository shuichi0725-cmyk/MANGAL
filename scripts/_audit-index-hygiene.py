#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""索引衛生監査(2026-07-14 検索改修と同時新設。ドリフト再発防止ゲート)。

検査(fail=exit 1 → 週次preflightがビルドを止める):
  1. 一覧索引のフィールド集合 = ビルダーのLIST_FIELDSと一致(スキーマドリフト検知)
  2. cover全行がslim形(楽天prefix付きフルURLの混在=短縮漏れ 0件) ※2026-07-13の6,100件ドリフトの再発防止
  3. authorsがパック文字列形(旧オブジェクト形式の混在 0件)
  4. head索引: 存在・フィールド一致・全slugが本体に存在・人気順(先頭要素のpopularity>=末尾)
  5. alt索引: 存在・dict形
  6. 行数レポート(本体 vs head vs alt。異常な激減=前回比>10%減 は警告)

使い方: python scripts/_audit-index-hygiene.py [DATA_DIR=data]
"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = sys.argv[1] if len(sys.argv) > 1 else "data"
BASE = os.path.join(ROOT, D)

EXPECT_FIELDS = [
    "slug", "title", "title_kana", "subtitle", "cover", "year_started", "year_ended",
    "status", "authors", "original_authors", "genres", "themes", "demographic",
    "publisher", "publishers", "magazine", "awards", "anime_adapted", "total_volumes",
    "max_edition_volumes", "latest_date", "first_volume_date", "popularity", "score",
    "fl", "_slugfix_new",
]
RK_PRE = "https://thumbnail.image.rakuten.co.jp/@0_mall/"

fails = []
warns = []

lp = os.path.join(BASE, "manga-list-index.json")
if not os.path.exists(lp):
    print(f"FAIL: 一覧索引なし {lp}"); sys.exit(1)
li = json.load(open(lp, encoding="utf-8"))
f = li["f"]; rows = li["d"]

# 1. フィールド集合
if f != EXPECT_FIELDS:
    fails.append(f"フィールド不一致: 索引={f} 期待={EXPECT_FIELDS}(ビルダーとこの監査の両方を更新すること)")

ic = f.index("cover") if "cover" in f else None
ia = f.index("authors") if "authors" in f else None
full_cover = 0; obj_author = 0
for row in rows:
    if ic is not None:
        c = row[ic]
        if c and isinstance(c, str) and c.startswith(RK_PRE):
            full_cover += 1
    if ia is not None:
        a = row[ia]
        if a and isinstance(a, list) and a and isinstance(a[0], dict):
            obj_author += 1
# 2. cover slim全行
if full_cover:
    fails.append(f"cover短縮漏れ {full_cover}行(楽天prefix付きフルURL混在=slim_coverドリフト)")
# 3. authorsパック形
if obj_author:
    fails.append(f"authors旧形式(オブジェクト) {obj_author}行(パック文字列に未移行)")

# 4. head索引
hp = os.path.join(BASE, "manga-list-head.json")
if not os.path.exists(hp):
    fails.append("head索引なし(manga-list-head.json)")
else:
    hi = json.load(open(hp, encoding="utf-8"))
    if hi["f"] != f:
        fails.append("head索引のフィールドが本体と不一致")
    slugs = {r[f.index("slug")] for r in rows}
    missing = [r[hi["f"].index("slug")] for r in hi["d"] if r[hi["f"].index("slug")] not in slugs]
    if missing:
        fails.append(f"headに本体不在slug {len(missing)}件(例 {missing[:3]})")
    ip = hi["f"].index("popularity")
    hd = hi["d"]
    if len(hd) >= 2 and (hd[0][ip] or 0) < (hd[-1][ip] or 0):
        fails.append("headが人気順でない")

# 5. alt索引
ap = os.path.join(BASE, "manga-alt-index.json")
if not os.path.exists(ap):
    fails.append("alt索引なし(manga-alt-index.json)")
else:
    ai = json.load(open(ap, encoding="utf-8"))
    if not isinstance(ai, dict):
        fails.append("alt索引がdict形でない")

# 6. 行数(前回比の激減検知: .cacheに前回値を控える)
marker = os.path.join(ROOT, ".cache", f"index-hygiene-lastcount-{D.replace('/', '_').replace('.', '')}.txt")
prev = None
if os.path.exists(marker):
    try: prev = int(open(marker).read().strip())
    except Exception: pass
if prev and len(rows) < prev * 0.9:
    warns.append(f"行数が前回比10%超減({prev}→{len(rows)})。大量skip/データ消失を疑う")
os.makedirs(os.path.dirname(marker), exist_ok=True)
open(marker, "w").write(str(len(rows)))

print(f"一覧 {len(rows)}行 / head {len(json.load(open(hp, encoding='utf-8'))['d']) if os.path.exists(hp) else 0}行 / cover短縮漏れ {full_cover} / authors旧形式 {obj_author}")
for w in warns: print("WARN:", w)
if fails:
    for x in fails: print("FAIL:", x)
    sys.exit(1)
print("索引衛生: OK")
