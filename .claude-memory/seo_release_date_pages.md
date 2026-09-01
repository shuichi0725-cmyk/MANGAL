---
name: seo-release-date-pages
description: "「漫画 発売日」検索の着地面(2026-09-01実装): /shinkan/YYYY-MM月別静的頁+/shinkan/this-week+/shinkan/next-month+解説文+sitemap。源=public/shinkan/{ym}.json(週次step1生成)。公開は機能蒸留/週次"
metadata: 
  node_type: memory
  type: project
  originSessionId: 191494c6-0eb5-4cbb-817a-a2afd70f0a40
  modified: 2026-09-01T23:16:25.540Z
---

2026-09-01 ユーザ相談「漫画 コミック 発売日 探す でGoogleから来てほしい」→ 調査で判明した穴と是正(commit 5f3dc9ad6)。

## 穴(実測)
- `/shinkan`(今月の新刊)は client fetch 描画で**静的HTMLの可視文字492字・本文「読み込み中…」**=Googleに空。月は`?m=`切替で月別URL無し。sitemap未登録。
- 作品頁は既に強い(頁別title/description「最新刊N巻はYYYY年M月D日発売」・ComicSeries+Book JSON-LD 2026-08-06)。

## 是正(4点)
1. **月別静的頁** `app/shinkan/[ym]/page.tsx`(generateStaticParams=public/shinkan/*.json実在月・dynamicParams=false)。題/巻/著者/出版社/レーベル/書影/Amazon/詳細リンクをHTMLに焼き、ItemList(Book+datePublished)JSON-LD(上限300)。前後月ナビ+日付アンカー。
2. **固定URL** `/shinkan/this-week`(build時の月〜日・JST。★client `ShinkanWeekList` が閲覧時に週が進んでいればJSONから差し替え=データ週の面HTML凍結対策) / `/shinkan/next-month`(build時の翌月。`ShinkanStaleNotice`で月跨ぎ案内)。
3. `/shinkan`(対話面)の下に**静的月ナビ**(`ShinkanMonthNav`)+**解説文**(`ShinkanAbout`=出典/毎週更新/発売予定日の注意)。sitemap: fixed に shinkan/this-week/next-month、dyn に月別。
4. 作品頁 description: 未来日→「発売予定」、完結作→「最終巻N巻は…発売」(旧=完結作は日付を出さなかった)。
- 共有部品: `lib/shinkanDates.ts`(純粋・client可)/`lib/shinkanData.ts`(fs・server)/`components/ShinkanRow.tsx`(Row+DayBlock、フック無し=両用)。ShinkanClient自体は未改修(見た目同一のRowを複製)。

## 運用
- 源JSONは週次step1 `shinkan` stepが再生成→月別頁は**フルビルド/機能ビルドで焼き直し**。データ週は面HTMLが前週のまま(this-weekはclient保険あり)。
- 検証= `_deploy-feature.py --dry`(staging+機能ビルド)。★detach起動のps1をbash printfで書くとバックスラッシュ+U / バックスラッシュ+f がエスケープ扱いで壊れる=Writeツールで書く。
- 残レバー: 外部被リンク(ユーザ側)/Search Consoleでの /shinkan 系URL登録リクエスト。

関連: [[seo_index_coverage_state]] [[seo_title_suffix_decision]] [[browse_ssr_shell_and_seo]]
