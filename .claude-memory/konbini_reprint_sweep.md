---
name: konbini-reprint-sweep
description: コンビニ判(秋田トップコミックスW/500・Gコミックス)純構成頁の一掃 2026-07-29。148頁drop・16頁hold(オリジナル疑い)・一律imprintパターン化は不可
metadata: 
  node_type: memory
  type: project
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-28T21:17:43.962Z
---

ユーザ発見「ザ・ベスト・バウトオブ刃牙=コンビニ疑い」(2026-07-29)から型化した一掃。

- **検出法**: 種2 editions.imprint が `Akita top comics%`/`%トップコミックス%`/`Gコミックス` のISBN集合を取り、**全冊該当の頁(純コンビニ頁)**をISBN索引で抽出。R9浄化(carrier遮断)の後に走らせたことで編頁の正体が露出した(バキ最凶死刑囚編31→7冊=全部トップコミックスW)。
- **結果**: 純165頁 → **drop148**(層A=スペシャル/ベスト/セレクション等の明白再編集114 + 層B裁定=アンソロ・テーマ編・改題廉価34) / **hold16** / 混入20頁=対象外。non-manga-drop.yml(reason=konbini_reprint)+nonmanga-drop-changelog記録・バックアップ=.cache/konbini-a-bak-*。
- **★hold16**(.cache/konbini-b-hold.json、コンビニ判だがdrop不可と裁定): 新装版仁義S8冊(正規仁義Sの唯一実体)/本気!サンダーナ/昭和都電物語(池田邦彦描き下ろし)/ダイモンズ(米原秀幸)/キク(高橋ヒロシ)/Gコミ描き下ろし型上下巻(極道の将器/遥かなる旗へ/爆風三国志/三匹の侍/不動丸)/十津川警部犯罪レポート9冊 等。**日文Gコミックス・秋田トップコミックスにはコンビニ判オリジナル新作が実在する**ため、**imprint一律dropパターン化は不可**(だからページ単位drop)。
- 改題廉価の罠: 東京直下震度7!!=「メトロ・サヴァイブ」改題 / 真説佐々木小次郎伝=「大江戸ジゴロ」SP。題が変わるので題ベース検出は効かない=imprint起点が正。
- 混入20頁(本編頁にコンビニ版ISBNが混ざる型)は未処置(number-dedupで概ね旧版優先になるため実害小・per-case領域)。
- 関連: [[exclusion-priority-policy]] [[inclusion-edge-rules]] [[isbn-dup-cleanup-state]](R9 carrier遮断が本件の露出装置)
