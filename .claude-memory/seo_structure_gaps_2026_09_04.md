---
name: seo-structure-gaps-2026-09-04
description: 2026-09-04 アクセス向上の構造相談=実測(28日訪問230・Google20/Bing30閲覧)と穴7点の順位。1(ジャンル面title)・2(作品頁チップ→/genre)は適用済(c44360ea9・機能蒸留待ち)、3以降は未着手
metadata: 
  node_type: memory
  type: project
  originSessionId: 981cfdce-d412-49dd-a505-855ea2bffe35
  modified: 2026-09-04T05:32:14.860Z
---

ユーザ相談「mangalの構造でアクセスを上げるためにやっておいた方が良いこと」(2026-09-04)。
実測(cf-analytics web 28日): 訪問230 / 閲覧1,350、流入は内部遷移1,120・直接180・**Bing30・Google20** = 検索にまだ載っていない。

## 穴(効果順)と状態
1. ✅ **ジャンル面32頁のtitleが全部既定**(`MANGAL — 日本の漫画データベース`・description共通) → `app/genre/[key]` generateMetadata で件数/完結数/代表作3つから title(`◯◯漫画 おすすめ一覧（人気順・N作品）`・「4コマ漫画」等は漫画二重にしない)/description/OG を生成。commit c44360ea9。
2. ✅ **作品頁66k枚→ジャンル面への可視リンク0本**(ジャンルチップが `/browse?genre=`=クライアント描画の行き止まり) → `/genre/[key]` へ。同commit。★`components/DailyBits.tsx` のジャンルリンクは `/browse?genre=` のまま(ホームは別途32本の/genre/リンクを持つので未変更)。
3. ⬜ **雑誌・年・出版社ハブ頁が無い**(データは在る: magazines.yml 65 / publishers.yml 819 / year全頁)。作品頁の雑誌・出版社・読者層・年チップも `/browse?` 行き止まり。雑誌65頁が最安、次が年代、出版社は上位100社程度。既存分類の掛け合わせ=タクソノミー不増。
4. ⬜ **ジャンル面が薄い**: 人気順120作+一覧リンクのみ、著者リンク0・他ジャンル横リンク0。「完結のみ」「年代別」サブ面が長尾の着地面。`data/seeds/genre-intros.yml` は1件/32。
5. ⬜ **著者頁2万枚の薄さ**(サンプル=作品3本+索引1本)。sitemap を2作以上に絞るか文脈を足すか、要裁定。
6. ⬜ 細部: `app/anime/page.tsx` と `app/anime/[season]/page.tsx` の title が `- MANGAL` 自書きで**二重サフィックス**(08-31是正の取りこぼし)。`/list` は静的HTMLに作品リンク0本+汎用title のまま sitemap/フッターに残置。
7. ⬜ 作品頁の重さ: HTML 197KB + JS 563KB、RSCペイロード24チャンク重複。中期。

## ユーザ側スイッチ(未実施)
- Cloudflare **Crawler Hints**(IndexNow自動通知・無料・1クリック)+ Bing Webmaster Tools に sitemap。Bing流入>Google の現状では即効。
- 本番待ちの機能蒸留(/shinkan静的化・ナビ改訂・本件1,2)を出し、GSCで /shinkan 系URL登録リクエスト。

**Why:** 外部被リンクを待つ間に、クローラが辿れる内部構造と着地面ごとのtitleを増やすのが自力で効く唯一の柱。
**How to apply:** 3以降に着手する時はこの順で。コード変更は機能蒸留で本番へ(sitemapは週次)。関連: [[seo_index_coverage_state]] [[seo_release_date_pages]] [[seo_title_suffix_decision]] [[inflight_state_2026_09_01]]
