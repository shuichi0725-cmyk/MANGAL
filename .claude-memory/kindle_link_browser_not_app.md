---
name: kindle-link-browser-not-app
description: 【✅解決2026-07-29・10-15再試験】Kindleボタン=ブラウザで開く問題の確定解: App Links奪取の決め手は最終URLのパス(/dp=ブラウザ・検索系=全部アプリ)。302/JS遷移は無関係。★10/15に検索6形(/-/ja/s・/gp/aw/s・wwwなし・Chrome名指しintent等)も全部アプリ=Kindleを題名検索でブラウザに出す道は無い。実装=紙/dp直リンク+「Kindle版」誘導
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
  modified: 2026-10-15T04:28:45.648Z
---

★2026-07-29 実機検証(本番Worker /go-testページ・ユーザAndroid実機)で**確定解決**。積年の仮説を全部塗り替えた:

**実測マトリクス(決定打)**:
- amazon.co.jp の検索URLは**全形式アプリに奪われる**: /s?k= も /gp/search も /s/?field-keywords= も全滅。
- **商品ページ /dp/ だけブラウザで開く**。
- **302中継(/go)の有無は無関係**(302経由でも直リンクでも結果同一)。= 旧仮説「JS遷移なら安全」「サーバー302なら安全(マンバ解剖)」は**どちらも誤り**。マンバがブラウザで開けるのは302だからでなく**着地が/dp/だから**。
- 楽天(hb.afl→books.rakuten)は検索でもブラウザ ✓。Yahoo(shopping.yahoo.co.jp/search)はアプリに開くが**紙はアプリ内で買えるので問題なし**(規約NGは電子のみ)。

**採用実装(VolumeCoverflow.tsx)**: Kindleボタン=**紙の/dp/ISBN10直リンク(tag付き)** = links.amazonと同一。商品ページ内の形式切替「Kindle版」で電子へ誘導(サブタイトルに明記)。一度ブラウザで開けば以後のタップもブラウザ内に留まる。電子版ASIN(B0…)はDBに無いため検索経由が使えない以上これが唯一のブラウザ完結ルート。ISBN無し巻のみ検索fallback(アプリに開くが稀)。

**最終ボタンマトリクス(2026-07-29ユーザ実機確認済・全着地)**:
紙=楽天:ブラウザ(intent試行→市場アプリ非受理でfallback。ユーザ「ブラウザで問題なし」裁定) / Yahoo:アプリ(元から・紙はOK) / Amazon:**アプリ**(intent://+専用scheme com.amazon.mobile.shopping.web)。
電子=Kindle:**ブラウザ**(/dp直) / Kobo:ブラウザ。Androidのみクリック時intent切替・iOS/PC/非JSはhttpsのまま(hydration不一致回避)。

**掃除済(2026-07-29)**: Worker の /go 302中継+/go-test は撤去・デプロイ済(404確認)。★AffiliateLink.tsx/VolumeTile.tsx は**未使用の死にコード**(どの頁からもimportされず・旧/go+JS遷移仮説の残骸。schema `kindle_asin` フィールドは既在=ASINハーベストの受け皿)。残る削除候補=旧Worker「mangal」(要ユーザGO)。

## ★2026-10-15 再試験(ユーザ「Kindle/実本リンクで犬のエラーが出る頁がたくさんある。題名検索にできないか」)
- 犬の画面 = Amazonの404(「アプリに問題が発生しました CS11」)。原因は変換バグでなく **ISBN-10の/dpが Amazonに存在しない**(こんにちはマイコン1巻 4091041019 = 1982年刊・紙の商品頁なし。Kindle版は別商品 B0CW1B581M「まんが版 こんにちはマイコン(1)」で実在)。
- 実機(Android 10・Chrome)で13本タップ: /dp(Kindle B0…・紙ISBN10)=**ブラウザ**(7月と同じ)。
  Kindle題名検索 **6形すべてアプリ**: `/s?k=` / `/-/ja/s` / `/gp/aw/s` / wwwなし / **Chrome名指しintent(package=com.android.chrome)もアプリ** / `/gp/redirect.html?location=` は**404(犬)**。
  紙の題名検索(普通・アプリ指定intent)=アプリで目当て上位(紙はアプリでよいので使える)。
- 結論: **Kindleをブラウザで開ける道は /dp だけ**。ISBN(/dp)は捨てられない。Kindle版ASIN(B0…)が無い巻=紙の頁も無い巻は、Kindleボタンで救えない(手でASINを入れるか、Creators API解錠を待つ)。
- 危ない巻の推定(Amazonは止め札で照会しない。楽天書影の出どころで代用): 紙=楽天ブックス書影 211,215(79%)/ 楽天に登録・画像なし 8,407 / **Kobo電子のみ 15,776** / **どちらも無し 33,314**。下2つを含む頁 18,387・全巻が下2つの頁 14,368(2026-10-15 isbn-page-index 基準)。
- ★試験頁は2026-10-15 テスト環境に一時設置→結果受領後に削除済み(`public/lab/amazon-link-test.html`)。再試験するなら git 履歴から戻せる。

**★次段=Kindle ASINハーベスト(PA-API解錠後)**: マンバがKindle頁へ一発直行できる種明かし(ユーザ推理2026-07-29で確定的)=**各巻のKindle版ASIN(B0…)をDBに持ち /dp/B0…?tag= の普通の商品URLを作っているだけ**。正規入手路=PA-API(SearchItems×KindleStore、題+巻で照合)。mangal08-22の**180日3成果条件クリアでPA-API解錠**([[openbd-eol-amazon-required]]の書影と同じ解錠条件)→ Kindle ASIN収穫(楽天ハーベストと同型)→ Kindleボタンを電子版/dp直行に進化。現行の「紙/dp→Kindle版選択」はそれまでの暫定解。
