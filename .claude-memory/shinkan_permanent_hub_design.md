---
name: shinkan_permanent_hub_design
description: 【裁定・実装済】/shinkan は恒久URL+月を含まないtitle/h1、月はh2。競合2社(ほんのひきだし/gameiroiro)も同型。★日付でのリダイレクトは却下(平均10.1位の唯一のハブ資産を賭ける価値なし)
metadata:
  type: project
---

2026-09-18 ユーザ裁定+実装(commit d5fc3eb1d)。「漫画 新刊」「発売日」を受ける面の設計。

## 実測の出発点

**「漫画 新刊」「新刊」「発売日」系クエリでの表示は、GoogleもBingも90日間ゼロ**だった。
理由はマークアップに出ていた: 旧 `/shinkan` は title も h1 も「**2026年9月の**新刊」で、
**恒久的に「新刊発売日一覧」を名乗るURLが1枚も無かった**。

## 競合2社は同じ構造だった(実測)

| | title / h1 | 月の置き場 |
|---|---|---|
| hon-hikidashi.jp/news/lineup/ | 「コミック 新刊発売日一覧」 | h3(旬で3分割した記事へのリンク集) |
| calendar.gameiroiro.com/manga.php | 「漫画コミック 発売日一覧」(サイト名接尾辞すら無し) | **h2** |

★**2社とも title/h1 に月を入れていない**。gameiroiro は他の月を同じパスのクエリ
(`?year=&month=`)に置き、title も description も1ページ目と同一・canonical 無し =
**月別はインデックスされなくてよい捨て面**と割り切っている。
なお両社とも本文は薄い(hon-hikidashi 1,920字・canonicalタグ無し)= **作りは勝因ではない**
([[competitor_mangaseek_teardown]] と同じ結論)。真似するのは「恒久的な語を持つ」ところまで。

## 採った形

- `/shinkan` title=「漫画の新刊発売日一覧」 h1=同じ h2=「2026年9月の新刊」。description からも月・冊数を除去。
- `ShinkanMonthView` に optional `subheading` を追加(/shinkan だけが渡す。`[ym]`・`next-month` は不変)。
- ★**旧仕様は最大6日間「嘘のタイトル」を配信していた**(10月になっても次の週次まで「2026年9月」)。
  恒久語なら嘘にならない。これが変更の一番大きな動機。

## ★却下した案: 日付でリダイレクト

「`/shinkan` を押したら当月の日付URLへ自動で飛ばす」= Worker に数行で実装可能(既に301を3種類やっている)。
**却下**。理由:
- `/shinkan` は **ホーム以外で唯一まともに順位がついているURL**(90日で58表示・3クリック・**平均10.1位**、
  全52クリック中3)。CF実訪問でも4位(30日50閲覧)。内部リンク元6箇所以上。
- 301は論外(毎月ちがうURLへ評価を渡す)。302も長期化すると301扱いされうる = **賭け**。
- 得られるのは「最大6日のリンク遅れの解消」だけ。Googlebot 58req/日・`/shinkan` の表示は90日で58回
  という規模で、数日のズレは効かない。**賭けに見合わない。**

## 積み残し

- `/shinkan` は **3.34MB**(月別 `/shinkan/2026-07` は 4.43MB)= サイト最重量。
  恒久ハブ化(索引+直近数件に痩せさせ、全件は日付URLへ)は**未実施**。今回は文言だけ変えた。
  ほんのひきだしのように**旬(1〜10日/11〜20日/21〜31日)で分割**する案もあるが、
  「面を増やしても登録は増えない」が実測で確定しているので**SEOではなく表示速度/UXの改修**として扱うこと。
- `/shinkan/this-week`・`/shinkan/next-month` は移動するエイリアスのまま(sitemap収録中)。noindex 化は未実施。

関連: [[seo_index_coverage_state]] [[seo_release_date_pages]] [[seo_title_suffix_decision]]
