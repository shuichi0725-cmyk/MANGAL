---
name: cloudflare_analytics_access
description: Cloudflare Worker アクセス解析の叩き方(トークン=.env・GraphQL workersInvocationsAdaptive)
metadata: 
  node_type: memory
  type: reference
  originSessionId: a2ed548f-4b21-42ea-9ad0-229054bf2d45
  modified: 2026-07-29T07:44:21.707Z
---

**やり方の正 = skill `cf-analytics` + `scripts/_cf-analytics.py`**(2026-07-10 script/skill化=ユーザ依頼。ここは事実の記録のみ)。

Cloudflare のアクセス解析が叩けるようになった(2026-07-09 ユーザがトークン作成)。

- **トークン**: `.env` の `CF_ANALYTICS_API_TOKEN`(テンプレ「分析およびログを読み取る」=Analytics/Logs Read)。gitignore済み・**絶対commitしない**。★旧名`CLOUDFLARE_API_TOKEN`はwranglerが.env自動読込でdeploy認証に誤用(権限不足でError 10000=「CFトークン認証壊れ」の正体)→2026-07-29改名。deploy認証はOAuth(`wrangler login`)。
- **account_id**: `774e95ed884a48e76ffb5aa78ae7e037`(= [[deploy_environments_state]])。
- **本番Worker名**: `mangal-r2`(R2配信)。
- **叩き方**: `https://api.cloudflare.com/client/v4/graphql` に GraphQL。dataset=`workersInvocationsAdaptive`、fields=`sum{requests errors subrequests}` dimensions=`{scriptName date}`、filter=`datetime_geq/leq`。検証は `/user/tokens/verify`。
- ★**Web Analytics=設置済だった**(2026-07-05 ユーザが自動セットアップ。私が2度「未設置」と誤断→ユーザ指摘で判明 2026-07-10): **訪問者数・人気ページ・流入国・refererが取れる**。GraphQL `rumPageloadEventsAdaptiveGroups`(siteTag=806671887a234f4882f85ba92058da5f)。RUM REST(site_info)は403=scope外だがGraphQLは現行トークンで通る。
- リクエスト数≠訪問者(R2は1ページ=複数ファイル取得)は依然真=Worker系(report)の読み方。
- **現状(2026-07-10)**: Worker=7日30万req(クロール支配・エラー率0.006%)。人間=週66訪問・トップは/(53)・Google流入8が出始め・US31/JP18。

## ★subcommand は4つ(skill文書から2つ欠けていた → 2026-09-22 追記済)
`verify` / `report`(Worker) / `web`(人間RUM) に加えて **`bots --date YYYY-MM-DD`**(UAを検索クローラ/AI/SNS/攻撃/人間に分類)と
**`paths --date YYYY-MM-DD --bot <UA部分文字列>`**(そのbotが実際に取ったパスをステータス+分類つきで)がある。
Freeプランは **1日幅までしかクエリできない**ので bots/paths は日付指定が必須。

## ★2026-09-22 実測ベースライン(次回「様子を見る」時の比較元)
- 人間(RUM): 7日=閲覧1,152/訪問203、30日=3,040/510、90日=4,340/1,160。JP72%/CN21%。流入元=内部82%・直接14%・**Bing31 / Google5**。
- Worker: 30日 1,349,601req / エラー8件 = **0.001%**(5xx 0・Bing側もtimeout0/robots遮断0)= 配信は健全。
- ★**日次reqの山は毎回「単一クローラの波」**。人間でも障害でもない: 9/20の64,489= **PerplexityBot 48,072(74%)**・
  9/15の124,469= **YandexBot 45,252 + GPTBot 30,618**。平常日(9/22 2,945)は人間1,194/**Semrush系1,490(50%)**。
  → 山を見たら真っ先に `bots --date <その日>` を引く。requests の増減をサイトの調子と読まない。
- ★PerplexityBot は1日48,072reqの**64%を `/browse` 1枚**に投げていた(9/18に `Disallow: /browse?` を入れた直後)。Perplexity からの流入は90日で0。
- 検索エンジン28日: **Bing クリック304/表示3,490/CTR8.71%**(前半14日 90/990 → 後半14日 **214/2,500** = 約2.5倍で伸長中) vs **Google クリック9/表示172**。
- ★RUM の30日/90日窓は**10刻みに丸められる**(7日窓のみ実数)。小さな増減を読まない。
- GSC被覆は [[seo_index_coverage_state]] の 2026-09-17 実測(n=1,280)と同じ絵(n=1,317で登録4.3%・未発見65%・catch有無で差なし・ハブ60%)。
