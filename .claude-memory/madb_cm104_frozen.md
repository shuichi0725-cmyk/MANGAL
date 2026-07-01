---
name: madb-cm104-frozen
description: MADB cm104/cm105(シリーズ/雑誌master)は2024-11-25で凍結。cm101(巻)のみ月次更新。補完は恒久策
metadata:
  type: reference
---

★**MADBのファイル別更新頻度は同期していない(2026-06-01 定義的に確認)**:
- **cm101(単行本/巻)** = ★毎月更新。 最新1.2.16(2026-05-22)で dateModified 2026-05-18・最新刊2026-06発売まで収録。 2025-01以降の新刊19,367件。
- **cm504(作者master)** = 新鮮(2026-05)。 新作の作者C-idも解決可(虚構推理の新C429607/609等)。
- ★**cm104(単行本シリーズmaster)= 2024-11-25で凍結**。 最新1.2.16のcm104も139,130件・max dateModified=2024-11-25(古いDLと同一)。 虚構推理C357981 も numberOfItems=9のまま。 **再DLしても無意味**。
- **cm105(雑誌master)/cm103** = 同様にNov 2024で凍結。

**帰結(設計の核心)**:
- ★cm104/105は「frozen な部分参照」と割り切る。 ★**月次蒸留で再DLして鮮度を期待しない**(無駄)。
- cm104は **シリーズ単位の著者役割タグ([原作]/[漫画])を2024-11以前の作品しか持たない**。 新作はcm101のschema:creator(タグ無・カナ混入。 [[author_roles_state]]の虚構推理vol23+ケース)しか無い。
- ★だから **AniList著者補完(746)・MADB安全補完・種4 trailing補完は「応急処置」でなく恒久的な正解**。 MADBが永遠に埋めない領域を埋めている。
- ★**著者ゼロ・末尾欠けは毎月増える**(2024-11以降の新作が累積)→ enrich(AniList照合/著者補完/synopsis/作品QID)+種4 trailingは**月次蒸留の必須ステップ**。
- masterの更新頻度はMADB次第なので、 蒸留時に各ファイルの内部max dateModifiedをログして凍結状況を監視するとよい。 関連 [[project_architecture_seeds]] [[series_fragmentation_rootcause]]。
