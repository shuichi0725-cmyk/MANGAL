---
name: dead_search_index_retire_pending
description: 【✅完了2026-08-03】manga-search-index.json(11.3MB死蔵)は廃止済。残務=次回週次でR2実体削除のみ
metadata:
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-02T23:08:31.022Z
---

★**`manga-search-index.json` は 2026-08-03 ユーザGOで廃止実行済み**(呼び出し元ゼロの死蔵・86.6%重複だった)。

## 実施済み(コミット済)

- クライアント死蔵コード削除: `useSearchIndex`/`fetchSearchIndex`/`decodeSearch`(useMangaIndex.ts)、`matchText`/`searchMatches`(filters.ts)、`MangaSearchItem`型(schema.ts)、matchTextテスト群。
- 生成停止: `_build-list-index.py` から SEARCH_FIELDS/sout 削除。
- ★**罠を処理済み**: `--update`(増分)時の **alt索引の永続層が検索索引ファイルだった** → catch と同型の「manga-alt-index.json 自ファイルから非変更作を取り込む」方式へ付け替え。smoke実測: alt 46,051件完全保全・冪等。
- 6スクリプト+CI除名: `_r2-sync.py` / `_deploy-feature.py` / `_deploy-differential.py` / `_reflect-targeted.py` / `_weekly-preflight.py` / `_build-list-index.py` + ★**`.github/workflows/deploy-preview.yml`**(cp行=見落とすとpreviewデプロイが落ちるところだった)。
- 実体削除: data/(非追跡)・public/・.preview-data/ の3コピー。.gitignore の該当2行も整理。
- doc: `_gen-data-spec-pdf.py` 節削除、weekly/monthly SKILL.md の保留節を撤去。
- 検証: tsc緑・vitest 262全緑・py_compile緑・残存参照grepゼロ。

## 残務(1件だけ)

- ★**次回週次蒸留で R2 実体を削除**: `wrangler r2 object delete mangal-site/manga-search-index.json`。
  即時削除しない理由=古いタブの旧JSがまだ参照しうるため「全頁焼き直し後に消す」が安全策。
  手順は weekly-distill SKILL.md「次回週次での一回きりタスク」節に記載済み(完了したらその節ごと消す)。

## 将来メモ

- 検索索引が唯一広かった `au` 列の差分1,311件(企業・訳者・キャラ原案)は未回収。人物検索を広げたくなったら**一覧索引の著者欄にロール付きで足す**のが筋(索引復活はしない)。

関連 [[lightweight_index_architecture]] [[search_perf_hotspots_2026_08]] [[index_lightening_plan]]
