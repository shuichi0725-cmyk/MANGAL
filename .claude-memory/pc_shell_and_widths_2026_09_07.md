---
name: pc-shell-and-widths-2026-09-07
description: 【機構・全頁適用】PC共通シェル=ナビをlayoutへ一本化+左レール(検索窓+絞り込みパネル)+器をmax-w-6xlに統一。ヘッダー/ナビ/シェルの3つが同じ器という不変条件と、器の所在がcomponent側にある罠
metadata: 
  node_type: memory
  type: project
  originSessionId: 6b3b0423-d631-4891-b6d1-2dd77c1ad478
  modified: 2026-09-07T13:07:28.522Z
---

2026-09-07。ユーザ相談「PCで見られている・ヘッダーのアイコンが離れすぎ・やっつけ感」から始まった PC 表示の全面是正。
**lg(1024px)未満は一切変えない**(モバイル完全不変)が全変更に共通の制約。

## なぜやったか(実測)

- `_cf-analytics.py bots` の**人間ブラウザ内訳**(別セッションが同日追加): デスクトップ **8,979** / モバイル **3,000**
  = **PCが人間トラフィックの75%**。閲覧上位も / 510 → /browse 310 → /list 80 で PC 面が主戦場。
- レスポンシブ指定はサイト全体で **sm:12 / md:32 / lg:5 / xl:1 = 計50箇所**しか無かった
  = スマホ1枚を引き伸ばしていただけ。「やっつけ感」は感覚でなく構造。

## 出来上がった形(★これが不変条件)

★**ヘッダー・ナビ・シェルの3つは同じ `max-w-6xl`(1152px)**。1つでも違うと右端が揃わず「はみ出し」に見える。
実際 1440px でシェルだけ広く、ロゴ/≡/使い方の外へ本文が出てユーザ指摘を受けた。

| 層 | 実体 | 器 |
|---|---|---|
| ヘッダー(ロゴ・≡) | `components/SiteHeader.tsx` | `mx-auto max-w-6xl px-4` |
| アイコンナビ | `components/GlobalNav.tsx`(**layout が描く**) | 帯は全幅・中身 `mx-auto max-w-6xl px-4` |
| レール+本文 | `components/PageShell.tsx`(**layout が描く**) | `mx-auto flex max-w-6xl gap-6` |
| 左レール | `components/FilterRail.tsx` | `hidden lg:block w-[260px]` |
| 本文列 | | 1152-32-260-24 ≒ **836px** |

- **ナビは layout に一本化**。旧 `DesignNav`(lib/homeDesign)と home の `D3Nav` を統合し、**47箇所**(app 46頁 + HubListPage)の `<DesignNav />` を全廃した。ホームだけ太線+paper地に出し分ける(usePathname)。
- **左レール = 検索窓(mangal>ターミナル調) + FilterPanel**。状態は URL が source of truth(既存の対称エンコーダ `filtersToSearchParams` ⇄ `filtersFromSearchParams`)。**/browse・/list に居る時は同パスへ replace(その場で絞り込み)/ 他頁は /browse へ push**。
- **PCの検索窓はサイト全体で左の1つ**: ホームのヒーロー窓 `lg:hidden` / /browse の右上窓は撤去 / /list の上部行 `lg:hidden`。モバイルは各頁の窓が唯一なのでそのまま。
- 頁の器は **2系統**に整理(それまで xl576 / 2xl672 / [720px] / 3xl768 / 4xl896 / 6xl1152 / 無し の**7種類**あった):
  - 一覧・グリッド系 = `lg:max-w-none` で本文列を埋める
  - 長文の読み物(about/privacy/terms/contact/AI書評) = 幅を保って `lg:mx-0` で左詰め

## ★踏んだ罠(次も踏む)

1. **器の所在が頁ファイルに無いことがある**。`/shinkan` の 720px は `components/ShinkanMonthView.tsx` にあった。`app/**/page.tsx` だけ grep しても見つからない。
2. **`lib/homeDesign.tsx` はクライアントから import できない**(`loadData`=fs を引き込む)。だから GlobalNav はアイコンのパス表を自己完結で持っている。
3. **`useSearchParams()` は Suspense 必須**(静的書き出しではフォールバックがHTMLに焼かれる)。FilterRail のフォールバックは**素のGETフォーム**にしてある(`fallback: null` は本文を捨てる= [[browse_ssr_shell_and_seo]])。
4. **中央寄せの二重掛け**。レールの右で頁が更に `mx-auto` すると左右に空白が出て「浮く」。器を持つ側を1つに決める。
5. **`<a>` の入れ子は不正HTML**。箱ごとクリックさせたい時は `role="link"` + 実アンカーの `click()`。

## 申し送り(未処理)

- FilterPanel は件数計算にフル索引(br後6MB)が要るので、**レールを出す全頁が初描画後にアイドルで索引を取りに行く**。PCのみ・描画は阻害しないが、潰すなら索引のファイル名バンプ+長期キャッシュ([[index_format_change_versioned_filename]])。
- ホーム本文が 640px → 836px に広がった(ヒーロー/コーナーは640px前提の設計)。間延びするなら本文だけ上限を戻して左詰め。
- `components/HomeSidebar.tsx`(旧リンク集レール)は home-design-11 がまだ使うので残置。

**Why:** PC が主戦場だと実測で判ったのに、器がバラバラでレールも無かった。ここを崩すと「はみ出し」「浮き」が即再発する。
**How to apply:** PC のレイアウトを触る時は必ず上の表の3つが同じ器かを先に確認する。新しい頁を足す時は器を自分で持たず PageShell に任せる。関連: [[seo_structure_gaps_2026_09_04]] [[filter_ui_todo_2026_09_05]] [[preview_deploy_pitfalls]]
