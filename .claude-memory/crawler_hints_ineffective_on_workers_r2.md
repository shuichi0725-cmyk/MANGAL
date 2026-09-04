---
name: crawler-hints-ineffective-on-workers-r2
description: 【一次情報で確定】Cloudflare Crawler Hints の発火条件は「ゾーンCDNキャッシュの cache-status MISS」。本番は Worker+R2 配信でゾーンcache設定が効かないため発火しない公算が高い(だから IndexNow 自前送信が要る)
metadata: 
  node_type: memory
  type: reference
  originSessionId: b13171da-074b-4da8-a8b5-905f74606a97
  modified: 2026-09-04T11:05:30.906Z
---

2026-09-04、mangal-db.com の Crawler Hints をダッシュボードで**有効化した**(Caching → 構成 → トグル。日本語UIでは Configuration = 「構成」)。
ただし **本番構成では発火しない公算が高い**。以下は公式ドキュメント原文で確認済み(推測で再調査しないこと)。

## 確定した一次情報

- 発火条件: 「Crawler Hints uses **cache-status MISS** to determine when content has likely been updated」
  = オリジンの内容更新ではなく**ゾーンCDNキャッシュのMISS**を見ている。Cloudflare自身が eng blog で「**naive signal on its own**」と表現。
- 「A Worker is a **zoneless entity** ... **No zone configuration for caching applies to Workers Caching**」「Workers run before the cache」
- 「The Cloudflare CDN **does not cache HTML or JSON by default**」
- etag / last-modified / コンテンツハッシュ差分は**将来計画**の記述で、導入済みではない。
- Crawler Hints docs・ブログには **Workers / R2 構成への言及が肯定・否定とも一切無い**(= 保証なし)。
- 利用者報告: community.cloudflare.com/t/workers-cache-and-crawler-hints/905206 「Crawler Hints don't work when using the Cache API in workers」(公式回答なし・自動クローズ)。
- キー管理: Crawler Hints は**ユーザのキーファイル設置が不要**(Cloudflareが代行)。IndexNow FAQ も
  「When your CMS, hosting provider, or SEO plugin supports IndexNow, you don't need a key file」「Cloudflare offers native IndexNow integration」。
  ただし**Cloudflareが内部でどうキーを持ち所有権証明しているかは非公開**。

## 帰結

- 有効化自体は無料・無害なので**そのまま残す**。ただし「これで通知が飛んでいる」と当てにしない。
- ★確実な経路は **IndexNow 自前送信**([[indexnow_self_submit]])。これが本番の主柱。
- 発火しているか確かめる手段は Bing Webmaster Tools の **IndexNow Insights** を数日見るのが唯一(未確認)。

関連: [[hosting_worker_r2_architecture]] [[indexnow_self_submit]] [[deploy_environments_state]]
