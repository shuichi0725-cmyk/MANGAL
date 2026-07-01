---
name: rakuten_out_of_stock_flag
description: 【重要・再発防止】楽天Books API は既定で在庫切れを除外。絶版/品切れ巻を拾うには outOfStockFlag=1 必須。これを忘れると旧巻・特装版が取れず取りこぼす
metadata:
  node_type: reference
  type: reference
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★**楽天ブックスAPI(BooksBook/Search等)は既定 `outOfStockFlag=0`=在庫品のみ**を返す。
絶版・品切れ(「ご注文できない商品」)は**除外される**。

- ★**`outOfStockFlag=1` を付けると在庫切れ含む全件**が返る(書影・価格・ISBN付き)。
- 実証(2026-06-17): 化物語を `title=化物語 booksGenreId=001001`、
  - outOfStockFlag=0 → count **13**(旧巻が消える)
  - outOfStockFlag=1 → count **46**(通常版全22巻＋特装版全22巻が揃う)。
- ★これを忘れると: 旧巻の通常版・特装版が取れず「楽天に無い」と誤判定する(今回 (a)書影欠落356 / (b)none555 の主因)。

## 帰結(やり直すべき処理)
- 特装版混入 修正 [[special_edition_fix_state]] の **(a)書影取得・(b)通常版ISBN特定は全て outOfStockFlag=1 で再実行**すべき(コードに付与済みか必ず確認)。
- 検索の網羅性問題: 楽天は `title`/`author` でも返却数に上限(著者90件/`title=化物語`は13件@flag0)。**outOfStockFlag=1 + booksGenreId + title** で実質網羅。なお全巻を確実には NDL併用が堅い。

## ★レート制限 = 約1リクエスト/秒(厳守)
- 楽天APIは **~1 req/sec**。0.2〜0.4秒間隔で叩くと **429(Rate limit)多発→結果が空で返り取りこぼす**(「検索で出ない」の主因の一つ=こちらの叩きすぎ)。
- ★スクリプトは **api()呼び出しごとに `time.sleep(1.0)` で throttle**(=約1req/sec ちょうど)。429時は指数バックオフ追加。
  ★余分な+0.1秒は件数次第で全体~10%の無駄(ユーザ指摘2026-06-18)=**1.0ちょうど**にする。
- 実害例(2026-06-18): redo2 を 0.35s間隔で回し title検索が空振り→採用17止まり。1.0s に直すと回収増。

## API メモ
- host: `https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404`
- 認証2要素: `applicationId`(UUID) + `accessKey`(pk_…) + Referer/Origin=許可ドメイン(.env.local: RAKUTEN_REFERER=https://github.com/)。
- 書影=`largeImageUrl`(noimage除外)。在庫切れでも `cabinet/<ISBN下4桁>/<isbn>.jpg` 構築URLでも取れる。
