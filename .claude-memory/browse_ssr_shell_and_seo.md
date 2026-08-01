---
name: browse_ssr_shell_and_seo
description: /browse がSuspense fallback=nullでサーバ描画0だった(白紙+SEO欠落)。静的シェルで是正済
metadata: 
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-01T11:20:37.024Z
---

★**2026-08-01: `/browse` がサーバ側で本文を1文字も出していなかった**(白紙 + SEO欠落)。是正済み。

## 症状(実測・可視テキスト量)

```
/               5,014字
/genre/action  16,814字
/browse           357字   ← ヘッダとフッタだけ
/list             477字
```
`/browse` は**ヘッダ・フッタ・メニュー・ショートカットの4箇所から張られた「検索」の入口**なのに、
見出しも検索窓もカテゴリタイルも HTML に無く、**JS が動くまで白紙**だった。クローラから見ても空。

## 根因

`app/browse/page.tsx` の `<Suspense fallback={null}>`。
HomeClient / CategoryHub が `useSearchParams()` を使うため静的書き出しでは Suspense が必須で、
★**ビルド時はフォールバックが HTML に焼かれる**★。それが `null` だったので本文が丸ごと消えていた。
= データに依存しない見出し・検索窓まで JS 待ちにしていた。

## 是正

- `components/BrowseShell.tsx`(サーバコンポーネント)を fallback に据えた。
  見出し + 説明文(**IndexSummary の正しい総数**)/ **素の GET フォーム**の検索窓(JS前でも `/browse?q=…` へ飛べる)/
  カテゴリ13タイル(素の `<a>` + 正しい件数)。クラス名を HomeClient・CategoryHub と揃えて hydrate 時に見た目が飛ばない。
- `metadata` に title / description を追加(従来 canonical のみ)。
  ★`app/layout.tsx` に `template: "%s | MANGAL"` があるので、**ページ側の title に "| MANGAL" を書かない**
  (初回ビルドで二重になった。ビルドして実物を見なければ気づけなかった)。
- 実測: 可視テキスト **357字 → 593字**、「全 68,724 件」が HTML に実在。

## 関連する未着手

`/list` も同様にサーバ側がほぼ空(477字)。ただしこちらは Suspense ではなく
**データがクライアント読み込みで描くものが無い**ため別要因。未着手。

## ついでの教訓

★**Next の静的書き出しでは「fallback を null にする」= 本文を捨てること**。
`useSearchParams()` を使う画面では必ず意味のあるシェルを置く。

関連 [[deploy_cache_swr_hid_the_fix]] [[search_perf_hotspots_2026_08]]
