---
name: dead_search_index_retire_pending
description: manga-search-index.json 11.3MBは死蔵(呼び出し元ゼロ)。廃止は週次/月次蒸留の前に再検討=ユーザ裁定
metadata: 
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-01T02:22:18.570Z
---

★**`manga-search-index.json`(11.3MB)は完全な死蔵**。廃止の判断は **2026-08-01 ユーザ裁定で「週次蒸留・月次蒸留の前に再検討」**として保留。
= 勝手に消さない。蒸留に入る前にこの件を出して可否を仰ぐ。

## 調査済みの事実(再調査不要)

- **呼び出し元ゼロ**: `useSearchIndex` / `fetchSearchIndex` / `decodeSearch` / `MangaSearchItem` / `matchText` / `searchMatches` を使う画面が存在しない。
  検索は `lib/clientSearch.ts`(一覧索引を共有)に統一済みで、この索引は旧世代の置き土産。
- **なのに毎蒸留で生成・R2へPUT・本番に常駐**(manifest に実在を確認)。
- **68,749行×6列を全行照合した結果**: slug/title/title_kana/alt は他ファイルと**100%一致**、`au`(著者名)は一覧索引と**98.1%一致**。
  → **11.3MB のうち 86.6% が完全な重複**。
- ★**固有列は `title_romaji`(13.4%)だけ**。しかもこれは**捨てた方式の遺物** — clientSearch は
  「romaji列は廃止。クエリ側で romaji→かな 変換して kana と照合」に切替済み(全件焼き込み→1語変換)。
- ★**唯一の実質差 = `au` が1.9%(1,311件)だけ広い**: 企業(カプコン)・訳者(小野耕世)・キャラクター原案(岸田メル)を含む。
  一覧索引の authors/original_authors は作者を意図的に絞っている。**復活させるなら索引復活でなく一覧索引の著者欄にロール付きで足すのが筋**。

## 廃止するときの段取り(安全側・未実行)

1. クライアントの死蔵コード削除 + `scripts/_build-list-index.py` の生成停止 +
   ★**索引名を持つ6本のスクリプトから除名**(`_r2-sync.py` / `_deploy-feature.py` / `_deploy-differential.py` /
   `_reflect-targeted.py` / `_weekly-preflight.py` / `_build-list-index.py`)。1本でも漏らすと「あるはずのファイルが無い」で蒸留が落ちる。
2. R2の実体削除は**次の週次蒸留**(全頁が焼き直され旧JSが消えた後)。

関連 [[lightweight_index_architecture]] [[search_perf_hotspots_2026_08]] [[index_lightening_plan]]
