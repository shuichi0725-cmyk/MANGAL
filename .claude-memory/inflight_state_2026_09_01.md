---
name: inflight-state-2026-09-01
description: 2026-09-01時点の本番待ち(機能蒸留待ち)一覧と公開後の手作業。検索残務2点+発売日SEO面(/shinkan静的化)+アニメ季節コーナー再結線
metadata:
  type: project
---

## 本番待ち(=「機能蒸留して」で出る。dry-run 3回 build OK・同期計画 約41,000 PUT)
1. 検索残務2点(64cac8eda): HomeSidebar の haystack/別名先読み + ListClient の useSearchParams 同期初期化(Suspense境界)。
2. 発売日SEO面(5f3dc9ad6→26918912b): /shinkan 静的化(今月焼き込み)+ /shinkan/YYYY-MM(23か月)+ /shinkan/this-week + /shinkan/next-month + 解説文 + 作品頁description(発売予定/最終巻)。詳細=[[seo_release_date_pages]]。
3. アニメ季節コーナー(データ): 結線3,282→3,440・2026秋37→52作・両載せ(薬屋/やはり俺)。view JSONは週次で再生成=週次で出る。詳細=[[animatetimes_season_source]]。
- preview には薬屋2頁/やはり俺2頁/まどマギ頁を投入済(subset 12頁前後)。

## 公開後の手作業(ユーザ)
- GSC URL検査で `/shinkan`・`/shinkan/this-week`・`/shinkan/next-month`・`/shinkan/2026-09`・`/shinkan/2026-10` を「インデックス登録をリクエスト」(1日10件前後)。
- sitemap は機能蒸留では更新されない(除外対象)=月別URLが載るのは**次の週次蒸留**。その後 GSC で sitemap.xml を再送信。GSC画面の「69,441/08-30」は週次前の旧読込=削除不要。

## 未決・宿題
- makai-tenshou(魔界転生とみ新蔵版)= promote が db-v2 で series not found → 8/21から再生成不能(anilist:false が届かない)。要検死。
- アニメ nopage台帳194件(登録候補)/ B13(OVA形式がハーベスト対象外=岸辺露伴型)。

## 追記 2026-09-02: /shinkan 年月ナビの固定2行化(年チップ1行+月行横スクロール+当月へ初期スクロール)= preview確認待ち→機能蒸留で本番へ(コードのみ: components/ShinkanMonthNav.tsx, app/shinkan/this-week/page.tsx)


## 追記 2026-09-02(夜): アップ直前リハーサル済み([[weekly_rehearsal_2026_09_02]])
- step1→preflight→CODE週判定→フルビルド42分→sitemap→`_r2-sync.py --dry --prune`(PUT 180,880/削除136)まで通した。**R2/KV/finalizeは未実行**=上記1-3は依然「本番待ち」。
- 本物の「週次蒸留して」の前にやること: ①未反映書影337頁の反映(`docs/production-diagnostics/cover-override-unreflected-2026-09-02.txt` を `_promote-bulk-v2.py --only-file`) ②アイドル書影ジョブ(`_placeholder-cover-refresh.py --all`)を止める ③`--prune` 必須(台帳41件・実削除40頁)。
- 連鎖alias3本(スゴ盛)は是正済(8de66d807)。ps1ラッパはUTF-8化済。
