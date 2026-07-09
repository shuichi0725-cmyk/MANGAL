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
- ★**Web Analytics=設置済だった**(2026-07-05 ユーザが自動セットアップ。私が2度「未設置」と誤断→ユーザ指摘で判明 2026-07-10): **訪問者数・人気ページ・流入国・refererが取れる**。GraphQL `rumPageloadEventsAdaptiveGroups`(siteTag=806671887a234f4882f85ba92058da5f)。RUM REST(site_info)は403=scope外だがGraphQLは現行トークンで通る。
- リクエスト数≠訪問者(R2は1ページ=複数ファイル取得)は依然真=Worker系(report)の読み方。
- **現状(2026-07-10)**: Worker=7日30万req(クロール支配・エラー率0.006%)。人間=週66訪問・トップは/(53)・Google流入8が出始め・US31/JP18。
