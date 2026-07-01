---
name: kindle-link-browser-not-app
description: 【残タスク・今は直さない】Kindle購入ボタンはAmazonアプリでなくブラウザ(Android=Chrome/iOS=Safari)で開かせる。アプリ内ではKindle本が買えないため(IAP規約)。PCは対象外
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-12 ユーザ要望(覚えておく、今は直さない)。

**何**: 電子書籍(Kindle)ボタン → Amazonアプリが開くと**Kindle本はアプリ内で購入できない**(Apple/GoogleのIAP規約でAmazonが購入機能を外している)ため、ブラウザで開かせたい。Android=Chrome / iOS=Safari。PCはどうでもよい。

**実装の手がかり(調査済みの一般知識、実装時に要検証)**:
- 直リンクだと App Links(Android)/Universal Links(iOS)で amazon.co.jp がアプリに奪われる。
- ★定石 = 自ドメインの中継ページ(/go/amazon/{asin})を挟み、**JSの location.href で遷移**させる: iOS SafariはJS発navigationではUniversal Linksを発火させない=Safari内で開く。Androidも多くの場合ブラウザ内に留まる。
- Android保険: `intent://www.amazon.co.jp/dp/{ASIN}#Intent;scheme=https;package=com.android.chrome;end` でChrome明示起動が可能。
- アフィリエイトtagの保持を忘れない([[store_affiliate_architecture]])。中継ページは広告PR表記の置き場としても都合が良い。
- 楽天Kobo等他ストアも同型の問題がないか実装時に確認。
