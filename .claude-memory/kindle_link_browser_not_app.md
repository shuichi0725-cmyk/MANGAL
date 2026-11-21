---
name: kindle-link-browser-not-app
description: 【★2026-10-15裁定=エラーを出さない>ブラウザで開く(名前検索・API解錠後に/dp直行へ戻す)】【✅解決2026-07-29・10-15再試験】Kindleボタン=ブラウザで開く問題の確定解: App Links奪取の決め手は最終URLのパス(/dp=ブラウザ・検索系=全部アプリ)。302/JS遷移は無関係。★10/15に検索6形(/-/ja/s・/gp/aw/s・wwwなし・Chrome名指しintent等)も全部アプリ=Kindleを題名検索でブラウザに出す道は無い。実装=紙/dp直リンク+「Kindle版」誘導
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
  modified: 2026-10-15T12:55:55.857Z
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

## ★★2026-10-15 ユーザ裁定: 「ブラウザで開く」より「エラー(犬の404)を出さない」を優先
ユーザ「ブラウザで開くよりエラーを出ない方を優先させた方が良いのではないか? 安定的に月10件売れるようになって API が使えるようになって
ブラウザで開けるようになるが正解な気がしている」= **旧方針「Kindleはブラウザで開くを死守」は格下げ**。順番は
①名前で検索してエラーを出さない(Android は Kindle もアプリで開く=アプリでは Kindle本を買えない、は割り切り)→ ②月10件の売上で Creators API 解錠
→ ③Kindle版ASIN(B0…)を集めて /dp/ 直行(ブラウザ)に戻す。
- 実装済み: 羅針盤のボタン(コマ・PCの右の欄)= `lib/amazon.ts` の `amazonNameSearchUrls(題名, 著者)` = 紙 stripbooks / Kindle digital-text。 ISBN を持たない(ユーザ「isbnは持たないで」)。
- 作品頁(VolumeCoverflow)= 2026-10-15 ユーザ GO「この方針で進めて」で実装: `hasRakutenPaper(cover_url)`(書影が楽天ブックスの紙の画像・書影なしgif含む = 約8割)の巻だけ
  ISBN-10 の /dp/(紙も Kindle も・ブラウザで開く)、それ以外は「題名 巻 著者」で検索(紙 stripbooks / Kindle digital-text)。 Kindle の箱の説明も「Amazonで探します」に切り替わる。
  特装版の Amazon も同じ規則。 本番に出るのは週次(全頁のコード変更 = CODE週)。

**★次段=Kindle ASINハーベスト(PA-API解錠後)**: マンバがKindle頁へ一発直行できる種明かし(ユーザ推理2026-07-29で確定的)=**各巻のKindle版ASIN(B0…)をDBに持ち /dp/B0…?tag= の普通の商品URLを作っているだけ**。正規入手路=PA-API(SearchItems×KindleStore、題+巻で照合)。mangal08-22の**180日3成果条件クリアでPA-API解錠**([[openbd-eol-amazon-required]]の書影と同じ解錠条件)→ Kindle ASIN収穫(楽天ハーベストと同型)→ Kindleボタンを電子版/dp直行に進化。現行の「紙/dp→Kindle版選択」はそれまでの暫定解。

## ★2026-11-21 Creators API 解錠 → Kindle版ASIN 直行の第1号が実機で成功
- こんにちはマイコン 1-2巻(紙頁なし=犬404だった巻)に Kindle版ASIN(B0CW1B581M / B0CW1JWZZZ)を入れてテスト環境へ → **ユーザ実機で「想定通りブラウザで開いた」**。
- 仕組み: seed `data/seeds/kindle-asin.jsonl`(isbn13→kindle_asin)→ `_promote-bulk-v2.py` 最終passの `_kindle_for` で巻に充填 → VolumeCoverflow は kindle_asin があれば `kindleDpLink`(/dp/B0…)。表示コードは元から対応済みだった。
- 次段 = 作者名で一括(searchItems author・KindleStore・1回10件・1検索最大100件)→ 100件超の作者だけ作者+題名で追加。照合は 題+巻番号+発売日(Kindleの publicationDate=紙の発売日)。 [[openbd-eol-amazon-required]]
- ★2026-11-21 作者10人の試行(`scripts/_kindle-asin-harvest.py trial`・呼出45回・出力 .cache/kindle-asin/trial-*): 自サイト332巻 → A(題+巻+日付±62日)80(24%)/ B 54 / なし198。
  学び: ①作者名検索はキーワード扱いで**名前によっては無関係な雑誌等を大量に返す**(佐藤元=総1000・みさきのあ=325、どちらも照合0)②作者欄の2人目(原作・解説者)で引くと外れる(滝瀬源一=のたり松太郎の原作)
  ③Kindleの発売日が**電子の配信日**の出版社がある(長谷川町子=2013/2020)= 日付照合だけでは取りこぼす ④多版の頁は別版の同番号に当たる(=Bは目視行き)
  ⑤**頁ごとの「題名+第1作者」検索**は確実(のたり松太郎36件・紙の日付一致)。ただし1頁1回以上=全7.1万頁で8日超。→ 作者一括(総数が小さく照合が取れる作者だけ)+頁ごとの題名検索の併用が本命。
- ★2026-11-21 頁モード試行(`_kindle-asin-harvest.py pages`・60頁130巻・呼出122): A 6 / B 30 / なし 94 / 紙の商品頁 有125 無0。
  ★取得前の項目調査(ユーザ「一緒に取れる情報を捨てて取り直した過去がある」)= 価格・在庫(offersV2)以外の全項目を取り、生の応答を
  `.cache/kindle-asin/raw/YYYYMM.jsonl.gz` に保存(販促の売り場分類だけ削る=1件80KB→数KB。122回で175KB)。
  取れる物: isAdultProduct(成人判定にそのまま使える)・役割つき著者・頁数・publicationDate(紙の発売日のことが多い)・releaseDate(電子の配信日)・売り場ジャンル・書影URL(手元のみ)。
  B の正体 = 電子の復刊(「マンガの金字塔」「カドカワデジタルコミックス」等)で Kindle の日付が配信日 = 巻番号は合っている。
  → B の採否は「頁の版の巻番号1..Nが Kindle 側で揃うか」で判定する案(未実装)。古い作品はそもそも Kindle が無い(なし94)。
  回数見積り: 頁ごとに Kindle検索1回+紙照会(10冊/回・頁をまたいでまとめれば全27.7万冊で約2.8万回)= 全体で約10万回 ≈ 12日(8,640回/日)。
- ★★2026-11-21 ユーザ「一番まずいのはやり直すことではなく、やりすぎて使えなくなること」= Creators API は**量より生存**。
  道具の安全側3点: 2.0秒間隔(公表1TPSの半分)/直近24時間の台帳 `.cache/kindle-asin/calls.log` で 1日8,000回(KINDLE_ASIN_BUDGET・★同日ユーザ裁定「3000はマージン取りすぎ・8000まで叩いてよい」)を超えたら止める/
  **429 が1回でも出たら取り直さず即停止**・非200が5連続で停止。 公表の初期上限 8,640/日は「最初の30日」だけで、以後は売上連動(5セントにつき1回/日)=
  売上が少ないと大きく下がり得る → 予算を数字で当てにしない。 試験用の手打ち道具(scratch の ca.py)は消した=API はこの道具だけから叩く。
- ★2026-11-21 15:40 **初の429**(`ThrottleException "Request rate limit exceeded"`)= 当日の呼出 約3,475回(実記録3,272+推定203)・直近1時間1,795回・止まる直前は0.5回/秒の一定ペース。
  = **公表の8,640/日より手前で止まった**(日量か時間量かは未確定)。道具は設計どおり取り直さず即停止。 収穫は1,016頁済(採る2,538巻/見直し197/なし1,255・紙 有3,952 無37)。
  次回: 翌日に同じコマンドで再開し、止まった回数で実際の枠を測る → 予算(KINDLE_ASIN_BUDGET)をその手前に合わせる。

