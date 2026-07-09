---
name: cf-analytics
description: アクセス解析して=Cloudflare Worker(mangal-r2)のリクエスト/エラー日別レポート。必ず _cf-analytics.py から(GraphQL再実装禁止)。訪問者/人気ページは取れない(Web Analytics未設置)
---

# Cloudflareアクセス解析 (= 2026-07-09 トークン設置・2026-07-10 script/skill化)

トリガー語: **「アクセス解析して」**(「アクセスどう?」等も同義)。

## やること (1コマンド)
```
python scripts/_cf-analytics.py report --days 7      # 日別 requests/errors/subreq + 合計/エラー率
python scripts/_cf-analytics.py verify               # トークン生存確認(失敗時の切り分け)
```
- endpoint/認証/GraphQL(workersInvocationsAdaptive)の正は **script に封じ込め済み=その場で再実装しない**(_lookup.py と同じ原則)。
- キー: `.env` の `CLOUDFLARE_API_TOKEN`(Analytics Read。★絶対commitしない)。account/Worker名はscript内定数(本番=mangal-r2)。

## 読み方の規律 (= 数字を誤読して報告しない)
- ★**requests≠訪問者**: R2配信は1頁閲覧=HTML+索引+書影etc複数リクエスト。さらに**クロール支配**(実測: 波が来ると日10万超、引くと日2千台)。「訪問者N人」とは絶対に言わない。
- 言えるのは: リクエスト総量の推移 / エラー率(平常0.01%未満。急増=配信障害signal) / クロール波の有無。
- **取れないもの**: 訪問者数・人気ページ・流入国(Web Analyticsビーコン未設置。設置=サイトへのJS追加=ユーザ裁定マター)。聞かれたら「取れない+設置すれば取れる」と答える。

## 使いどころ
- 週次蒸留後の健康確認(エラー率が跳ねていないか)・「最近アクセスどう?」への即答。
- 定期監視はしない(トラフィックが意味を持つ規模になるまで=ユーザ判断 2026-07-09)。

## 関連
- 事実の記録=memory [[cloudflare_analytics_access]] / 本番構成=memory [[deploy_environments_state]]
