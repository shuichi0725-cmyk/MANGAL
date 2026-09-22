---
name: cover-null-despite-seed
description: 【型・44頁是正済】covers seedに書影が在るのに頁がnull。掃引はISBN集合の突合10秒、直しはtargeted再promoteだけ
metadata:
  type: project
---

**発端(2026-09-22 ユーザ報告)**: 「うる星やつらの書影が全部出ない」。

**切り分けの順**(この順でないと的を外す):
1. `data/manga.v2/<slug>.yml` の `cover_url` を版ごとに数える → 全null なら**データ側**の問題
2. `covers.jsonl.gz` に当該ISBNが在るか → 在るなら**充填漏れ**、無いなら**源が無い**
3. 源が無い時は `_lookup.py --isbn` → 楽天に商品はあるが「書影無」= その版は元から画像が存在しない
4. 索引の `cover` は `cover_of()` が**全edition+全versionを走査**する。1枚も無い頁だけが一覧/検索でも空になる

**うる星の実際**: 少年サンデーコミックスは**刷タブが2種**あり、
`初版カバー(1980-87)` 34巻は楽天に画像が無い(★ユーザ裁定「通常版はもともとない」= 正常)。
`新装版カバー(2006-08)` 34巻 + ワイド版15 + 文庫版18 + 復刻BOX4 は**seedに在るのに頁がnull**だった。

**掃引(10秒・全DB)**: 全 `manga.v2/*.yml` を走り、`cover_url` が null で ISBN が
`covers.jsonl.gz`(URL有)に在り `cover-override.jsonl` の最終行が空でないもの = 未充填。
2026-09-22 実測 = **44頁 / 163巻**(うる星37 + ワイルド7 18 + 菜 18 + おやこ刑事10 + 手塚作品多数)。

**直し方**: `_promote-bulk-v2.py --only-file <stems>` だけで全部埋まる(再掃引で残0)。
そのあと `_reflect-targeted.py --only ... --push` → `_deploy-differential.py`。

★**原因は未特定**。`_COVERS` は1回ロードのキャッシュなのでseed差し替えでは説明がつかず、
44頁すべてが 2026-09-21 のフルpromoteの**同じ5分の書込み窓(08:40-08:45)+09:37の5件**に集中していた。
次の月次フルpromoteでログを取るのが確実。**フルpromote後は必ずこの掃引を回す**こと。
[[cover_tooling_traps_2026_09]] [[rakuten_cover_data_asset]] [[volume_add_includes_cover]]

★**「書影が無い」を全部穴と見なさない**: 刷(カバー違い)タブは装丁そのものを指す枠なので、
別の版・電子の書影で埋めてはいけない(うる星 `初版カバー(1980-87)` = ユーザ裁定で埋めない)。
掃引が出すのは「seedに在るのに頁がnull」だけで、**源が無い巻は対象外**=ここを混ぜない。
