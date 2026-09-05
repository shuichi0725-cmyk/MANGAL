---
name: filter_ui_todo_2026_09_05
description: 【実装済・preview確認待ち】検索フィルターUI改善5点(見出し沈み/件数のソート撤去/適用中チップの穴/0件と読込中/並べ替え+アコーディオン)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f118081-d8b9-4bb2-beaf-12d03c7f0a3e
  modified: 2026-09-05T03:32:39.624Z
---

2026-09-05 ユーザ相談 →**同日 5点すべて実装・push 済**(commit `1ec45e2d2`)。
残り = **preview 目視 → OK なら「機能蒸留して」で本番へ**(コードのみの変更なので feature-distill ルート)。

## 大前提(ユーザ裁定 2026-09-05)

- ★**機能の追加・削除・変更はしない**。UI/操作性だけ直す。
- 外部AIが勧めた「最近使った検索条件」(localStorage)は新機能なので**やらない**。
- 「選択中条件をチップ表示」「結果件数を常に表示」は元から実装済み(=現物を見ない一般論だった)。

## 実装したもの(commit 1ec45e2d2)

0. **見出し沈み**: `Section` 見出し `text-black/60` → `text-ink/70`(ベタ書きでテーマ変数を見ておらず、
   ダーク `theme-d3`=黒地で黒文字だった) / モーダル地 28%→**94%**(blur維持) / 件数バッジ /40→**/60**(0は/30) /
   `AuthorKanaIndex` の `hover:bg-black/5` → `var(--color-surface-2)`
1. **件数計算からソートを外す**: `lib/filters.ts` に ★**`filterItems`(並べ替え抜き)** を切り出し、
   `applyFilters = sortItems(filterItems(...))`。FilterPanel の `rowsFor` は `filterItems` を使う。
   ★実測(本番索引69,236件・6パス中央値)= **153ms → 78ms**、行数完全一致(130,821)。
   `searchSnapshot.test.ts` の facetCounts も同経路に揃えた(スナップショット不変)。
2. **適用中チップの穴**: 要素/出版社/連載誌/画集/**検索語**/並び順 を `active[]` に追加(key は `id` で衝突回避)。
   ブロックを **sticky**(PC=`top-14`=共通ヘッダーの下 / モーダル・抽斗=`top-0`。新propは `stickyTop`)+
   ブロック内にも「条件をリセット」(挙動は最下部と同一=検索語は残す)。
3. **0件と読込中の区別**: 新prop **`loading`**(HomeClient が `indexLoading||searchLoading||searchPending` を渡す。
   未指定は `data.manga.length===0` から推定)。読み込み中は件数バッジを出さず、**出版社/連載誌の0件落としも止める**
   (=「1社も無い」という嘘の廃墟を作らない)。確定後0件なら理由別案内(検索0ヒット→「検索語を消す」/
   絞りすぎ→「条件をリセット」)。
4. **並べ替え+アコーディオン**: 種類→連載状態→分野→ジャンル→創刊→要素→出版社→連載誌→著者→**並び順(最下部)**。
   下の重い5つ(創刊/要素/出版社/連載誌/著者)を折りたたみ、**選択が入っている節は自動で開く**、見出しに選択数/選択肢数。
   ★合わせて**内部スクロールを全廃**(要素 max-h-60 / 出版社 max-h-48 / 連載誌 max-h-48 / **著者一覧 max-h-56**)。
   著者一覧は memo に無かった4件目だが同じ「親が動くか子が動くか指で分からない」型なので同時に外した(**ユーザ確認事項**)。

## previewセット(2026-09-05)

★UI確認のため **人気順 上位200頁** を `.preview-data/manga` に入れ直した(commit `ea7508d2f`)。
それまで 0 頁で「漫画がなにもない」状態だった(2026-09-04 の解放 0d44c08ea 以降)。
選定= 本番一覧索引を popularity→score→year 降順(=`sortItems("popularity")` と同規則)。
公開slug→SRC stem 逆引き(slug-overrides.yml)を通すこと。書影200/200・人気度 330,034〜28,425。
★暦(`public/calendar`)は**古い月を消してから**作り直す(ビルダーは上書きのみで消さない=
982頁時代の月ファイル810本が死にリンクとして残っていた。本番は r2-sync が data/calendar で丸ごと差替=不影響)。

## 見てもらう時の確認ポイント(preview)

- 出版社を開くと **819行が全高で出る**(内部スクロール廃止の帰結)。長すぎるなら「上位N+もっと見る」に変える相談。
- 並び順が最下部でよいか(絞り込みでないので下げた)。
- 著者一覧の内部スクロール廃止の可否。

## 対象ファイル

`components/FilterPanel.tsx` / `components/AuthorKanaIndex.tsx` / `app/HomeClient.tsx` /
`lib/filters.ts`(`filterItems` 新設) / `lib/searchSnapshot.test.ts`。
`components/ListClient.tsx` は無改造(`/list` は `state.query` を消す設計なので検索語チップは出ない)。
