---
name: slug-collision-year-rule
description: 裸「-西暦」slugは禁止(バグ痕跡)。同名異作品の従版=姓+年。生成器3箇所修正済(2026-07-14)・見直し18件適用済
metadata: 
  node_type: memory
  type: project
  originSessionId: 6021a518-a36b-44ff-aa0c-31013be82fed
---

**slug末尾の裸西暦(shion-2026型)はバグの痕跡**。同名異作品の衝突は従版に**姓+発売年**を付ける。

- **なぜ再発したか**: 同じ「衝突したら-西暦」fallbackが3箇所にコピーされていた(draft lib/gen-preview/gen-midfill)。gen-previewはコメント「衝突=hold」なのに実装が西暦付与のまま。2026-07-14に3箇所とも撤去=裸西暦を作るコードは0。
- **現行の衝突処理**(gen-preview/gen-midfill): 著者ヨミ姓のローマ字+年を付す(`shion-hinasho2026`型・attached)。著者ヨミ無しは**hold**(previewに出さない)。
- **形式の並存(容認)**: 新規生成=attached(`takase2004`/CLAUDE.mdのmanabe1993型)。旧c1_sub衝突処理=hyphen(`waru-kagemaru-1977`/`daruma-yamanaka-1994`型)=既存は正としてそのまま。
- **本番頁のslug rename正規ルート**: ①manga.v2/preview両方rename ②`data/seeds/slug-overrides.yml`のoverrides節(`old: {slug: new}`形式=promote恒久・flat先頭部は別物) ③`data/slug-aliases.yml`(旧URL redirect。**既存aliasの連鎖直結**を忘れない=imajin→imagine-2020→新の型) ④両索引--update/--remove。
- 2026-07-14に西暦付き38件を全数点検: 姓+年16件・題の一部(don-quixote-2002)=正、裸西暦12件へ姓付与・無印化1(tenchi-muyou)・壊れ2(crisis-2050/c-minor)・年誤り2(egawa-2001/ochi-1994)・混在解明1(とよ田短編集)。

[[collision_slug_investigation]] [[slug_cluster_fix_and_changelog]]
