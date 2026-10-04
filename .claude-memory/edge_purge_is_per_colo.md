---
name: edge_purge_is_per_colo
description: 【型】週次のedge purge(Worker /api/purge=cache.delete)は要求を受けた拠点だけ=日本の拠点に旧HTMLが最大24h残る(2026-10-04 ホームだけ旧)
metadata:
  type: project
---

2026-10-04 週次後、ユーザ(日本・ブラウザキャッシュ消去済)のホームだけ旧(69,463作品・羅針盤なし)、/browse は新。
こちらの curl(別拠点)では / も /?v= も新(69,514・/compass あり・Age 9065)。

- 原因(公算大): `workers/r2-serve.js` は `caches.default` に HTML を s-maxage=86400 で焼く。Cache API は**拠点(colo)ごと**で、
  `/api/purge` の `cache.delete` は**その要求を受けた拠点だけ**消す。finalize の purge は手元近くの拠点しか効かない
  → 日本の拠点に週次前のHTMLが最大24時間残る。ブラウザ側の max-age は60秒なので端末キャッシュは無関係。
- 切り分け: `?v=任意` を付けると別キャッシュキー=最新が出れば拠点キャッシュ。
- 全拠点を消すには Cloudflare の purge API(ゾーン単位)= ダッシュボード「キャッシュ → 設定 → すべてパージ」か、
  Zone.Cache Purge 権限の API トークン。手元の鍵は CF_ANALYTICS_API_TOKEN(解析読み取り)と wrangler OAuth のみ=未保有。
- 恒久策案(未着手・ユーザ裁定待ち): Cache Purge 権限トークンを .env に置き、finalize の purge をゾーンの purge API(URL指定 or すべて)に切替。
関連 [[deploy_cache_swr_hid_the_fix]] [[rsc_txt_browser_cache_stale_navigation]] [[index_json_browser_cache_stale]]
