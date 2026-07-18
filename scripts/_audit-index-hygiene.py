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
  7. ★形式契約(2026-07-18 版ズレApplication error対策=[[index-format-change-versioned-filename]]):
     data/manga-*.json の形式署名を data/seeds/index-format-contract.json(git管理)と突合。
     同名のまま形式が変わっていたら FAIL =「ファイル名をバンプ+fetch側変更+--accept-format」を要求。
     旧ファイルはR2に残す(r2-syncはprune無し)ので旧JSは旧形式を読み続ける=デプロイ跨ぎ無害。
     加えて lib/ の fetch("/manga-*.json") 先が実在することを確認(改名の片割れ忘れ検知)。

使い方: python scripts/_audit-index-hygiene.py [DATA_DIR=data] [--accept-format]
        --accept-format = 意図的な形式変更/新ファイル追加時に契約を現状から書き直す(単独で明示実行)
"""
import glob as _glob
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCEPT_FORMAT = "--accept-format" in sys.argv
argv = [a for a in sys.argv[1:] if not a.startswith("--")]
D = argv[0] if argv else "data"
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

# 7. ★形式契約(同名での形式変更を禁止するゲート)
CONTRACT = os.path.join(ROOT, "data", "seeds", "index-format-contract.json")

def _jstype(v):
    if isinstance(v, bool): return "bool"
    if isinstance(v, (int, float)): return "number"
    if isinstance(v, str): return "string"
    if isinstance(v, list):
        inner = next((x for x in v if x is not None), None)
        return f"array<{_jstype(inner) if inner is not None else '?'}>"
    if isinstance(v, dict): return "object"
    return "?"

def _signature(path):
    """形式署名 = 中身の行数でなく「契約」だけを畳む({f,d}型=f列+各列型 / map型=値型)"""
    j = json.load(open(path, encoding="utf-8"))
    if isinstance(j, dict) and isinstance(j.get("f"), list) and isinstance(j.get("d"), list):
        cols = {}
        for i, name in enumerate(j["f"]):
            v = next((r[i] for r in j["d"] if i < len(r) and r[i] is not None), None)
            cols[name] = _jstype(v) if v is not None else "?"
        return {"kind": "fd", "f": j["f"], "coltypes": cols}
    if isinstance(j, dict):
        v = next(iter(j.values()), None)
        return {"kind": "map", "valtype": _jstype(v) if v is not None else "?"}
    return {"kind": _jstype(j)}

if D == "data":  # 本番索引のみ(previewはsubsetミラーなので対象外)
    cur = {os.path.basename(p): _signature(p)
           for p in sorted(_glob.glob(os.path.join(BASE, "manga-*.json")))}
    if ACCEPT_FORMAT:
        old = json.load(open(CONTRACT, encoding="utf-8")) if os.path.exists(CONTRACT) else {}
        json.dump(cur, open(CONTRACT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        chg = [n for n in cur if old.get(n) != cur.get(n)] + [n for n in old if n not in cur]
        print(f"形式契約を更新: {CONTRACT} (変更 {chg or 'なし'})。★同名での形式変更なら、これは誤り=ファイル名バンプが先")
    elif not os.path.exists(CONTRACT):
        fails.append(f"形式契約なし {CONTRACT} → 初回は --accept-format で登録")
    else:
        con = json.load(open(CONTRACT, encoding="utf-8"))
        for name, sig in cur.items():
            if name not in con:
                fails.append(f"契約未登録の索引 {name} → 新ファイルなら --accept-format で登録(fetch側の実装も確認)")
            elif con[name] != sig:
                fails.append(
                    f"★形式契約違反 {name}: 同名のままフォーマットが変わっている(版ズレでApplication errorになる型)。"
                    f"→ ファイル名をバンプ(例 {name.replace('.json', '.v2.json')})+fetch側(lib/)も変更+旧ファイルはR2に残す+--accept-format で新契約登録")
        for name in con:
            if name not in cur:
                warns.append(f"契約にあるが実体なし {name}(廃止したなら --accept-format で契約からも除去。R2の旧配信は残してよい)")
    # fetch側の実在確認(改名の片割れ忘れ)
    fetched = set()
    for src in _glob.glob(os.path.join(ROOT, "lib", "*.ts*")) + _glob.glob(os.path.join(ROOT, "components", "*.ts*")):
        for m in re.findall(r'fetch\("/(manga-[\w.-]+\.json)"', open(src, encoding="utf-8").read()):
            fetched.add(m)
    for name in sorted(fetched):
        if not os.path.exists(os.path.join(BASE, name)):
            fails.append(f"コードが fetch する {name} が {D}/ に無い(改名の片割れ忘れ)")

print(f"一覧 {len(rows)}行 / head {len(json.load(open(hp, encoding='utf-8'))['d']) if os.path.exists(hp) else 0}行 / cover短縮漏れ {full_cover} / authors旧形式 {obj_author}")
for w in warns: print("WARN:", w)
if fails:
    for x in fails: print("FAIL:", x)
    sys.exit(1)
print("索引衛生: OK")
