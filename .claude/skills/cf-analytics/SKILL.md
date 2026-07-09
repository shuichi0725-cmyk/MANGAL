---
name: cf-analytics
description: アクセス解析して=Cloudflare解析2系統(report=Workerリクエスト/エラー・web=訪問者/人気ページ/国)。必ず _cf-analytics.py から(GraphQL再実装禁止)
---

# Cloudflareアクセス解析 (= 2026-07-09 トークン・2026-07-10 script/skill化+Web Analytics対応)

トリガー語: **「アクセス解析して」**(「アクセスどう?」「人気ページは?」等も同義)。

## やること (2系統・質問に合わせて選ぶ)
```
python scripts/_cf-analytics.py web --days 7         # ★人間の訪問者: 閲覧/訪問/人気ページ/国/流入元
python scripts/_cf-analytics.py report --days 7      # Workerインフラ: 総req/エラー率(クロール込み=配信健康)
python scripts/_cf-analytics.py verify               # トークン生存確認(失敗時の切り分け)
```
- 「アクセスどう?」= **web が主役**(訪問者視点)、report は配信健康(エラー率)の補助。
- endpoint/認証/GraphQL(workersInvocationsAdaptive+rumPageloadEventsAdaptiveGroups)の正は**scriptに封じ込め済み=再実装しない**。siteTag等の定数もscript内。
- キー: `.env` の `CLOUDFLARE_API_TOKEN`(Analytics Read。★絶対commitしない)。RUM RESTは403=scope外だがGraphQL rumは通る(実証済)。

## 読み方の規律 (= 数字を誤読して報告しない)
- **web(ビーコン計測)=人間**: JS実行ブラウザのみ、bot/クローラは原則含まれない。設置=2026-07-05(自動セットアップ)以降のみ。
- **report(Worker)=機械込み**: requests≠訪問者(1頁=複数ファイル+クロール支配。波が来ると日10万超/引くと日2千台)。「訪問者N人」はwebの数字でのみ言う。
- エラー率(report)平常0.01%未満。急増=配信障害signal。
- 流入元「(直接)」=refererなし(ブックマーク/アプリ/一部ブラウザのプライバシー設定)。

## 使いどころ
- 週次蒸留後の健康確認(report のエラー率)・「最近どう?」への即答(web)。
- 人気ページ(web)は discovery/ランキング戦略の実データ源として蓄積中(2026-07-10時点: 週66訪問・Google流入が出始め)。
- 定期監視はしない(規模が意味を持つまで=ユーザ判断 2026-07-09)。

## 関連
- 事実の記録=memory [[cloudflare_analytics_access]] / 本番構成=memory [[deploy_environments_state]]
