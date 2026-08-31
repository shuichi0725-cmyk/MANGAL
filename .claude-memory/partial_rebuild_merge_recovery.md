---
name: partial-rebuild-merge-recovery
description: フルビルド一部欠陥の復旧=out退避→FEATURE_BUILD部分ビルド→対象dir+_next unionを合流(全再ビルド回避)
metadata: 
  node_type: memory
  type: project
  originSessionId: bd02af38-42f4-4acb-9f59-ae607bc37eeb
  modified: 2026-08-31T14:07:18.882Z
---

フルビルド(~1.5-3.5h)完走後に**非漫画面の一部だけ欠陥**が見つかった時、全再ビルドせず復旧する型(2026-08-31 /titles空ビルドで実証・~20分):

1. `Rename-Item out out.keep`(退避。node居座りを先にkill)
2. 原因データを直して `MANGAL_FEATURE_BUILD=1` で部分ビルド(manga66kはplaceholder 1頁=著者20k+面のみ生成)
3. 合流: 対象dirを `robocopy new→out.keep /MIR` + 対象ルートのhtml/txtコピー + **`out\_next` を /E でunion**(★これを忘れると新頁が参照するhashed chunkが無く壊れる。hash名は衝突しないのでunionは安全)
4. `Remove-Item out; Rename-Item out.keep out` → 枚数検証(manga数が不変なこと)

漫画頁側の欠陥はこの型では直せない(FEATURE_BUILDがmangaを作らない)=その時はフル再ビルド。
関連: [[build_input_wiring_three_places]] [[promote_hangs_on_exit_windows]]
