---
name: search-console-bing-api-access
description: GSC(_gsc.py)とBing Webmaster(_bwt.py)を直接読めるようにした(2026-09-15)。鍵の置き場・設定で踏んだ3つの罠・APIでは取れない層
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4cce8a9c-a5ff-4f2c-a19f-a21245d006b2
  modified: 2026-09-15T03:12:19.124Z
---

2026-09-15、**両方の検索エンジンのWebmasterデータをscriptから直接読める**ようにした。
道具 = `scripts/_gsc.py`(Google) / `scripts/_bwt.py`(Bing)。作法は `_cf-analytics.py` と同じ
(endpoint/認証の正はscript = 再実装禁止。通信は標準 urllib)。

## 鍵の置き場(公開リポジトリなので厳守)

- Bing: `.env.local` の `BING_WEBMASTER_API_KEY`(ポータルで発行するAPIキー1本のみ。OAuth不要=Googleより遥かに簡単)
- Google: `.env.local` の `GSC_SA_JSON` = **パスだけ**。鍵実体は `C:\Users\<user>\.gcp\mangal-gsc.json`(**リポジトリ外**)
- `.gitignore` の `.env*.local` で除外済み。[[repo_is_public_github]] なので鍵本体は絶対にrepo内に置かない

## 設定で踏んだ罠3つ(次回も必ず踏む)

1. ★**組織ポリシーがサービスアカウント鍵の作成をブロックする**
   (`iam.disableServiceAccountKeyCreation`。Googleが新しい組織に自動適用する「デフォルトで保護」)。
   → `console.cloud.google.com/iam-admin/orgpolicies/iam-disableServiceAccountKeyCreation` で
   「親のポリシーをオーバーライド」→ルール追加→適用**オフ**。対象がプロジェクト単位なら影響はそのプロジェクトだけ。
2. ★**鍵は PKCS#8**(`-----BEGIN PRIVATE KEY-----`)で降るが、`rsa` ライブラリは **PKCS#1 しか読めない**。
   → `_gsc.py` の `_pkcs8_to_pkcs1()` が DER の OCTET STRING を剥がす。依存は `rsa` だけ
   (google-auth / google-api-python-client は入れていない)。
3. ★**プロパティは `sc-domain:mangal-db.com`**(ドメインプロパティ)。
   `https://mangal-db.com/` を渡すと **403**。`verify` で必ず実物の識別子を確かめてから使う。
   権限は `siteRestrictedUser`(制限付き)で Search Analytics は読める。

## 取れるもの / 取れないもの

- GSC API: Search Analytics(クリック/表示/CTR/順位 × クエリ/ページ/国/デバイス/日付・16か月)、
  Sitemaps、URL Inspection(**1日2,000URL**)。
- ★**GSC APIで取れない**: 「インデックス作成」レポートの**内訳**(登録済み/未登録の理由別) / リンクレポート(被リンク) /
  Core Web Vitals。→ 内訳は**画面のCSVエクスポート**をユーザに出してもらう(2026-09-15 実際にそうした=
  これが無ければ「クロール済み-未登録が35件しかない」という決定的事実に辿り着けなかった)。
- Bing API: GetRankAndTrafficStats / GetQueryStats / GetPageStats / GetCrawlStats / GetCrawlIssues /
  GetUrlSubmissionQuota / GetLinkCounts / GetKeywordStats。`GetActiveSitemaps` は **404**(このテナント未提供)。
  日付は `/Date(エポックms)/` 形式。`AvgClickPosition == -1` は「クリック0で算出不能」であって順位ではない。

## 初回実測(2026-09-15)

Bing 直近14日 = クリック162 / 表示1,561 / CTR 10.4%(「日本漫画」で平均2.0位)。
GSC 直近28日 = クリック8 / 表示139。**Bingの方が10倍以上取れている**。
被リンクは Bing の LinkCounts が **0件** = 「高品質ドメインからのリンク不足」は警告でなく文字どおりゼロ。
→ 詳しい診断は [[seo_index_coverage_state]]

関連: [[cloudflare_analytics_access]] [[indexnow_self_submit]] [[ssr_content_gate]]
