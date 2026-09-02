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

## ★静的化完了(2026-09-01 午後・ユーザ裁定「静的ページのみで問題ない」→commit 7a2f85dad/f6fc99556/26918912b)
- ShinkanClient(client fetch描画)は**退役**。/shinkan=当月分をbuild時に焼く(可視492字→46,185字)。共通server部品 `components/ShinkanMonthView.tsx`(=/shinkan・/shinkan/[ym]・/next-month が共有)。
- 旧UXは client 小部品で維持: `ShinkanDayHeader`(sticky日付+日送り+fastScrollTo)/`ShinkanShare`/`ShinkanPageEffects`(?m=→月別頁へ置換遷移・?go=today今日ジャンプ=ホーム「全部見る」互換)/`ShinkanLive`(鮮度保険=JSON署名 `monthSignature` 比較で差し替え。差し替え時の「詳細」はbuild時既知slugのみ=404を撒かない)/`ShinkanStaleNotice`(月跨ぎ案内)。
- **canonical規則**: 常設URLが正(当月頁→/shinkan、翌月頁→/shinkan/next-month、過去月=自己)。JSON-LDは author を出さない(著者欄が「・」連結の表示文字列で分割不能)・urlは索引内slugのみ。robots: `Disallow: /shinkan/*.json$`。
- レビュー(ワークフロー): 1回目はSEOレンズのみ完走(残りはセッション上限で失敗)、2回目は2レンズ完走で**ユーザの使用量懸念により停止**→残りは手元確認。★教訓: サブエージェント多発は上限を食う(1回目709k tok)。以後この規模の変更はレンズ1〜2本+反証1体で足りる。
- 検証: dry-run(_deploy-feature.py --dry)3回とも build OK。★本番公開は「機能蒸留して」待ち(sitemapは週次)。
