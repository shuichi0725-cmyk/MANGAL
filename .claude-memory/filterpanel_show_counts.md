---
name: filterpanel-show-counts
description: 【✅完了 2026-06-13】FilterPanel全facet(連載状態/分野/ジャンル/出版社/掲載誌)に動的件数表示済。実装=FilterPanel.tsxのcounts(useMemo)+Cntバッジ
metadata: 
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

## ✅完了(2026-06-13 commit c092d880)
- 全facet(連載状態/分野/ジャンル/出版社/掲載誌)に**動的件数**(b案=「その値を選ぶと何件」)を併記。faceted-count = 当該facetだけ解除した state で applyFilters→残作品を値で集計、`useMemo`でstate変化時のみ再計算。0は淡色。
- ★**ブラウザJS計算=R2静的のまま**(サーバ化しない)。/list の初期100件設計では全DBがクライアントに無いので、本番では件数JSONをビルド時に焼くか全データ前提かを再確認(=[[monthly_intake_reality]] の件数チャンク)。
- 実装=`components/FilterPanel.tsx` の `counts`(useMemo)+ `Cnt` バッジ。typecheck通過、プレビュー未確認(promote完了後に実機で)。

---
【元依頼 2026-06-05】FilterPanel(`components/FilterPanel.tsx`)の**各フィルタ項目に該当件数を表示**する。

**現状**: 私が追加した「🎨 画集（161）」チップ**だけ**が件数を出している(`data.artBooks.length`)。 他のフィルタは数字なし。

**依頼**: ★**連載状態(完結/連載中/休載)・分野(少年/少女/青年/女性/児童/その他)・ジャンル(アクション/冒険/…)** 全てに、 画集チップと同じ形式で**該当作品数を併記**してほしい。 (出版社/連載誌/著者 も同様に出せるとなお良いと思われる=要確認だが、 まず上記3つ)。

**実装メモ**:
- 件数の出し方は `components/CategoryHub.tsx` が既に各カテゴリで `data.manga.filter(...).length` を出している(少年34等)= 同手法で per-value count を算出。
- 静的件数(各値の総数)か、 動的件数(他フィルタ適用後に絞られた数)かは要確認。 ★まず静的(CategoryHub同等)で良さそう。 動的だと selected state に応じ再計算が要る。
- ChipButton 等の label に `（N）` を付与。 0件の値は出さない/淡色化の判断も。
- 画集は別配列(data.artBooks)なので件数は別軸。 漫画フィルタの件数は data.manga ベース。

関連: [[art_book_inclusion]](画集チップ実装元)。
