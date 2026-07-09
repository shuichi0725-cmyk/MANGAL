---
name: cloudflare_analytics_access
description: Cloudflare Worker アクセス解析の叩き方(トークン=.env・GraphQL workersInvocationsAdaptive)
metadata: 
  node_type: memory
  type: reference
  originSessionId: a2ed548f-4b21-42ea-9ad0-229054bf2d45
---

**やり方の正 = skill `cf-analytics` + `scripts/_cf-analytics.py`**(2026-07-10 script/skill化=ユーザ依頼。ここは事実の記録のみ)。

Cloudflare のアクセス解析が叩けるようになった(2026-07-09 ユーザがトークン作成)。

- **トークン**: `.env` の `CLOUDFLARE_API_TOKEN`(テンプレ「分析およびログを読み取る」=Analytics/Logs Read)。gitignore済み・**絶対commitしない**。
- **account_id**: `774e95ed884a48e76ffb5aa78ae7e037`(= [[deploy_environments_state]])。
- **本番Worker名**: `mangal-r2`(R2配信)。
- **叩き方**: `https://api.cloudflare.com/client/v4/graphql` に GraphQL。dataset=`workersInvocationsAdaptive`、fields=`sum{requests errors subrequests}` dimensions=`{scriptName date}`、filter=`datetime_geq/leq`。検証は `/user/tokens/verify`。
- **限界**: Worker解析は**リクエスト数/エラー/CPU**まで。**訪問者数・人気ページ・流入国は取れない**(Web Analyticsビーコン未設置 or ログ解析が要る)。リクエスト数≠訪問者(R2は1ページ=複数ファイル取得)。
- **現状(2026-07-09)**: 7日で約30万req(大半クロール)・エラー率0.006%。ユーザ判断=「まだ数字を気にする規模でない、設定できたのでよし」。トラフィックが意味を持ったら「アクセス解析して」でレポート。ツール化は未実施(不要不急=作らない [[feedback_dont_inflate_work]])。
