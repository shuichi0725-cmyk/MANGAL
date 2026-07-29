---
name: kindle-link-browser-not-app
description: 【✅解決2026-07-29】Kindleボタン=ブラウザで開く問題の確定解: App Links奪取の決め手は最終URLのパス(/dp=ブラウザ・検索系=全部アプリ)。302/JS遷移は無関係。実装=紙/dp直リンク+「Kindle版」誘導
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
  modified: 2026-07-29T08:17:02.993Z
---

★2026-07-29 実機検証(本番Worker /go-testページ・ユーザAndroid実機)で**確定解決**。積年の仮説を全部塗り替えた:

**実測マトリクス(決定打)**:
- amazon.co.jp の検索URLは**全形式アプリに奪われる**: /s?k= も /gp/search も /s/?field-keywords= も全滅。
- **商品ページ /dp/ だけブラウザで開く**。
- **302中継(/go)の有無は無関係**(302経由でも直リンクでも結果同一)。= 旧仮説「JS遷移なら安全」「サーバー302なら安全(マンバ解剖)」は**どちらも誤り**。マンバがブラウザで開けるのは302だからでなく**着地が/dp/だから**。
- 楽天(hb.afl→books.rakuten)は検索でもブラウザ ✓。Yahoo(shopping.yahoo.co.jp/search)はアプリに開くが**紙はアプリ内で買えるので問題なし**(規約NGは電子のみ)。

**採用実装(VolumeCoverflow.tsx)**: Kindleボタン=**紙の/dp/ISBN10直リンク(tag付き)** = links.amazonと同一。商品ページ内の形式切替「Kindle版」で電子へ誘導(サブタイトルに明記)。一度ブラウザで開けば以後のタップもブラウザ内に留まる。電子版ASIN(B0…)はDBに無いため検索経由が使えない以上これが唯一のブラウザ完結ルート。ISBN無し巻のみ検索fallback(アプリに開くが稀)。

**残骸**: Worker(r2-serve.js)の /go 302中継と /go-test 実験ページは**用済み**(ボタンはもう使っていない)。害はないが次回Worker整理時に撤去してよい。旧Worker「mangal」(Workers Builds残骸・ドメイン無し)も削除候補。
