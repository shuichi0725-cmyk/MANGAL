---
name: filter_ui_todo_2026_09_05
description: 【全実装済・機能蒸留待ち】検索フィルター一式(UI5点+巻数フィルター+/list 3件+死にprop+Esc+共有フック化)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f118081-d8b9-4bb2-beaf-12d03c7f0a3e
  modified: 2026-09-05T03:32:39.624Z
---

2026-09-05〜06。**この束は全部実装+push 済**。残り = **preview 目視 → 「機能蒸留して」で本番へ**(コードのみ=feature-distill)。

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

## 6. 巻数フィルター(2026-09-05 ユーザGO・commit `12afa94af`)

★UI磨きとは別に**機能追加を1つ**入れた(ユーザが質問→GO)。区切り= **1のみ/2-5/6-10/11-15/16-20/21+**、選択はOR。
★基準は **`max_edition_volumes`(= 一番巻数の多い版1本)= カードの「全N巻」と同じ数**。索引もpromoteも不要だった。
- `total_volumes` は**全版の合算**(SLAM DUNK 75/キングダム100)なので分類に使えない。
- ★**「一番最初に出た版の巻数」は不採用**(検討して捨てた): 複数版4,525頁で計算自体は可能(失敗0)だが、
  maxとバケツが変わる105頁を見ると初出版側が壊れている(子連れ狼2/鉄腕アトム3/餓狼伝1/湘南純愛組2)。
  「最古の発売日を持つ版」は**日付が数巻ぶんしか入っていない別版**(other/新装版/文庫版)を拾う。
- ついでに **巻数ソートの不一致を是正**: `lib/filters.ts` の `totalVolumes()` だけ total を返しており、
  ホームの「巻数(多い順)」がカード表示(HubRow)や `/list`(listSort.volCount)と別の数で並んでいた → max に統一。
- 件数集計は6→7パス(80ms→101ms。ソート撤去前の153msより速い)。テスト6件追加(vitest 291件緑)。

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

---

## 2026-09-06 追加分(ユーザが preview を見ながら次々指摘 → 全部是正済)

| 症状 | 実体 | commit |
|---|---|---|
| ホームの「連載中」がタイル7,431 / 帯7,438で食い違う | 帯だけ `status !== "completed"` で**休載7作を含めていた**。両方のリンク先は `?status=ongoing`(厳密)=数字が飛び先と不一致 | `1005f903f` |
| 旧デザイン3面(05/08/11)も同じ行 | 厳密一致へ。★完結を `manga.length - ongoing` の引き算で出すのをやめる(厳密化した瞬間に完結が休載を吸う) | `a251869d2` |
| `/list` のフィルター件数が全件基準 | `matchedSlugs` 未配線 **かつ** `filterItems` が `state.query` 非空時しか見ない二段構え。`/list` は query を FilterState に写さない設計なので渡しても無視されていた → **matchedSlugs は渡されたら常に効く**に変更 | `0ba2d2e9b` |
| `/list` ドロワーの並び順が効かない | 最後に必ず `sortRows` が上書き。`showSort=false` で非表示 | 同上 |
| `/list` の画集チップが空振り | ListClient は `state.artBooks` を読まない。`showArtBooks=false` + URL由来の artBooks も落とす | `2a285603b` |
| `/list` ドロワーのリセットだけURLが残る | `setState` → `applyState`。上部リセットとは元から挙動が違った | 同上 |
| `/list` に見えない「フィルター(1)」 | `activeCount` の `if (k === "sortKey")` が**存在しない旧キー名**で一度も発火せず、並び順が絞り込み1件に数えられていた → `"sort"` | `7dddba86b` |
| 画集チップの件数が定数161 | `applyArtBookFilters(...).length` に(検索語と年は効くので不一致だった) | `16e9bbeb1` |
| チップに押下状態が無い | `ChipButton`に`aria-pressed` / `ChipLink`に`aria-current` | 同上 |
| タップ後の待ち | 件数7パス=**実測100ms**(一覧の絞込+ソートは22ms)。`useDeferredValue` で件数だけ後ろへ。0件バナーは追いつくまで出さない | `03374595a` |
| `yearBounds` が死にprop | 2026-07-07 に年UIが創刊ドリルダウンへ置換された時の取り残し。両画面が69,236件を1周(7.1ms)して誰も使っていなかった。★`yearMin/yearMax` の**フィルター自体は現役**(作品頁が `?yearMin=` へリンク)なので関数は残す | `4165718d0` |
| `CoverImage` の `size` prop | no-op を10箇所が渡していた → 撤去。詳細は [[cover_resolution_policy]] | `7dddba86b` |
| フィルターが Esc で閉じない | サイト全体で Escape 対応は `CoverLightbox` だけだった。同じ作法+`role="dialog"` を両モーダルへ | 同上 |

★**根本原因と恒久策**: 上の `/list` 3件は全部「同じ FilterPanel を2画面が別々に手配線」が原因。
**`lib/useFilterPanelData.ts`(共有フック)に一本化済み**(`00bce3994`、挙動不変)。
索引ロード/検索の一致集合/確定前フラグ/著者50音をここに集約。**以後 prop を足すならここに足せば両画面に効く**。
画面差は引数3つだけ(`withCatch` / `query` の出どころ / `authorsReady`)。

## previewセットの現状(2026-09-06)

★**無作為3,000頁**(`random.seed=20260905`、commit `93b35a9a4`)。旧=人気順200頁は退場。
ファセット= 出版社224 / 連載誌33 / 要素203 / 著者2,723。巻数バケツは6つとも埋まっている。
検索テストの目印= 進撃の巨人 / 地獄楽 / 聲の形 / リライフ / マギ / BORUTO(★ONE PIECE は抽選漏れ)。
容量の考え方と再生成3点は [[preview_deploy_pitfalls]]。
