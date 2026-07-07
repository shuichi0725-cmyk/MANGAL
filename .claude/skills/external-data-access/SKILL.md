---
name: external-data-access
description: 楽天/NDL/キャッシュの照会は必ず _lookup.py から。レート事故(429/IP遮断)とキャッシュ理解の往復を根絶する
---

# 外部データ照会 (= 楽天・NDL・キャッシュ)

## 鉄則
- **照会はまず `python scripts/_lookup.py`**(キャッシュ層→--liveの順が内蔵)。楽天/NDLのlive呼び出しコードを**その場でコピペ再実装しない**(endpoint/header/レートの正は _lookup.py に封じ込め済み)
- **1.3秒/req 厳守・429=即中断**(NDLは回復するので慌てず1時間単位で休ませる。並列probeで悪化させた前科あり)
- **NDL不在≠不存在**(BL・小出版はNDL収録が弱い=不測ノ恋情の教訓)。実在確認の一次手段は**楽天live(outOfStockFlag=1)**
- 大量照会の前に「キャッシュで済むか」を必ず先に確認(下の資産マップ)

## 使い方
```
python scripts/_lookup.py --isbn 9784091204417                # キャッシュ層のみ(即答+delta1-3分)
python scripts/_lookup.py --isbn A,B,C --live                 # 複数=delta1パス共有→無い分だけlive
python scripts/_lookup.py --title "うる星やつら" --max 20 --live
python scripts/_lookup.py --creator "ひおあきら" --title "宇宙戦艦ヤマト"  # ★作者束縛NDL(古典/同名多発の全巻回収)
```
- ★**`--creator`(作品名+作者名でNDL SRU束縛)**=ユーザが手作業でやっていたNDL Search→TSVエクスポートの代替(2026-07-08)。`--title`だけでは楽天liveのみでNDLを叩かず、松本零士版/2199等の人気同名作に埋もれる(ひおあきら版ヤマトの教訓)。**版(seriesTitle)ごとに巻を束ねて表示・著者複数取得**(アンソロ/原作+作画の判定にそのまま使える)。古典・アンソロ・教育系の全巻/版回収はこれが本命。
- ★**APIに無く標準WebFetchも弾かれるサイト**(潮出版社usio.co.jp等の公式・静的ページ)は `python scripts/_tinyfish.py fetch <URL>`(無料Fetch)。e-hon等セッション必須の検索は無料Fetch不可=有料Browser領域(要ユーザ承認)。[[tinyfish_web_fetch]]

## キャッシュ資産マップ (= どのファイルに何が入っているか。★往復根絶の核心)
| ファイル | key | 入っているもの | ★入っていないもの |
|---|---|---|---|
| .cache/isbn-title-map.json (37万) | ISBN13 | **題のみ** | 日付・書影・価格・著者 |
| .cache/rakuten-isbn-delta.jsonl (830MB) | 行内isbn | **full item**: salesDate/largeImageUrl/itemPrice/author/publisherName/seriesName/itemCaption/booksGenreId | 在庫切れで未収穫の巻 |
| data/seeds/covers.jsonl.gz (30万) | **isbn13/cover_url**(キー名注意) | 書影URL | それ以外 |
| .cache/isbn-page-index.json (25万) | ISBN13 | 描画中の本番頁slug | ★鮮度注意=大変更後は `_exists.py --build` |
| .cache/volgap-ndl.jsonl | slug | NDL全巻正データ(巻抜け調査の土台) | — |
| .cache/db-v2.sqlite | — | 種2(series/editions/volumes)。series_key逆引き | 種2に無い巻(それが種4の領域) |

## live仕様の要点 (= _lookup.py 実装済み。修正時のみ参照)
- 楽天: `openapi.rakuten.co.jp/.../BooksBook/Search/20170404` + **Referer/Origin header必須**(無しやapp.rakuten直=400)。applicationId+accessKey+**outOfStockFlag=1**+formatVersion=2
- 楽天Kobo(電子版・書影補完用): `openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426` 同じReferer/Origin/レート。title+巻でlargeImageUrlが取れる(紙の欠け巻補完=skill kobo-covers)。noimage除外必須
- NDL SRU: `ndlsearch.ndl.go.jp/api/sru` recordSchema=dcndl。**一般語のtitle単独クエリはtimeout**(「臨場」型)→creator束縛を優先・timeoutはスキップ続行可。
- ★**NDLページングは大物で必須**(2026-07-05実害): 1リクエスト最大200件。数百版ある作(009/おそ松/バカボン)は`startRecord=1,201,401…`で総件数(numberOfRecords)まで**全ページ取得しないと原版を静かに取りこぼす**。1頁だけ取る実装は禁止。ループ=`while start<=total: start+=200`。
- ★**dcndl:BibResourceの断片割れ**(2026-07-05): レコードが2要素に割れ原版のISBNとvol/dateが泣き別れる型あり。「isbnのみ断片」を直前の「title/vol/date断片」に縫合するmerge_fragments処理を入れる(band-intruder-swapが手本)。
- 書影CDN構築URL: `thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/<ISBN下4桁(チェックディジット除く)>/<ISBN13>.jpg?_ex=200x200`(在庫切れでも取れる。使用前にHEADで200確認)

## 大量ハーベスト(数百件超)をする時
- 逐次追記(1件ずつflush)+再開可能(done-set)+429即中断、の3点セットを必ず入れる(_ndl7_fetch.pyが手本)
- 事前にユーザへ件数と所要を予告
