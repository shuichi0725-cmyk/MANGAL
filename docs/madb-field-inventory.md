# MADB JSON-LD field inventory (= 仕様書 vs 現状コード coverage)

> 文化庁 MADB (Media Arts Database) Ver. 1.0 仕様書 (= 2021-03-22) に定義された
> 全 property URI を、 現状の MANGAL コードベースで extract / 部分活用 / 未活用
> の 3 status に 分類した一覧。
>
> **作成日**: 2026-05-23
> **base にした仕様書 PDF**: https://github.com/mediaarts-db/dataset/blob/main/doc/MADB%E3%83%A1%E3%82%BF%E3%83%87%E3%83%BC%E3%82%BF%E3%82%B9%E3%82%AD%E3%83%BC%E3%83%9E%E4%BB%95%E6%A7%98%E6%9B%B8%EF%BC%88Ver.1.0%EF%BC%89.pdf
>
> **状態**: pdftotext で抽出した URI list と既存コードの cross-reference は完了。
> 仕様書本文 (= 各 property の **適用クラス / 多重度 / 値型 / 定義原文**) は
> PDF の表組内 日本語テキスト が pdftotext で 抽出できない (= font CID encoding
> 問題、 pdftoppm 未 install) ため **未確定**。 自宅 PC で poppler install 後
> に Read tool で 各 page を 画像読みして 各表に追記する想定。

## 全体集計

| カテゴリ | URI 数 | 備考 |
|---|---:|---|
| **schema.org** 系 (= 標準 vocabulary) | 90+ | Book/CreativeWork/Person 等の汎用属性 |
| **purl.org/dc/terms** 系 (= Dublin Core) | 4 | contributor / creator / publisher / relation |
| **w3.org rdf-schema** 系 | 1 | rdfs:label のみ |
| **mediaarts-db.bunka.go.jp/data/property** 系 (= MADB 固有) | **150** | series / 巻号 / variant / 関連作品 等の独自 拡張 |
| **合計** | **約 245** | 全 entity (Manga / Animation / VideoGame / Item / Series / Magazine / Agent) 共通の dictionary |

manga 関連 entity (= MangaBook / MangaBookSeries / MangaMagazine / MangaMagazineIssue / MangaMagazinePublication / Agent) で 適用される property は 全体の **約 60-80** と推定 (= 仕様書 PDF 読破時に 適用クラス column で 確定)。

## 現状コードベースで extract している property (= 計 17 種)

`lib/madb-jsonld.ts` (= MangaBook record の typed 抽出) + `scripts/_build-series-v2.py` (= MangaBookSeries record の cluster build) で 引いている key の和集合。

### `@id` / `@type` / 基本 metadata

| URI / key | 用途 | コード位置 | downstream |
|---|---|---|---|
| `@id` | MADB entity URI (= "M..." / "C..." / "A..." 等の suffix 抽出に利用) | `lib/madb-jsonld.ts:401` extractMadbId | `volumes.madb_book_id` (= UNIQUE), series cluster id |
| `@type` | entity class (= class:MangaBook / class:MangaBookSeries 等) | fixture でのみ確認 | (現状: filter には未使用、 stream 側で 既に絞られて来る前提) |
| `rdfs:label` | entity の人間可読 ラベル (= 単行本 title 等) | `lib/madb-jsonld.ts:50`, `_build-series-v2.py:261` | series cluster の base / subtitle 分離 |

### schema.org 系 (= 13 種)

| URI | 用途 | コード位置 | downstream |
|---|---|---|---|
| `schema:contentRating` | "成年コミック" 文字列 (= 1 次 adult filter) | `lib/madb-jsonld.ts:51, 407` | `isAdultMadbRecord` の rating signal |
| `schema:description` | 概要 string (= 2 次 adult filter で "成年コミック" 部分一致 check) | `lib/madb-jsonld.ts:54, 411` | `isAdultMadbRecord` の description signal |
| `schema:isbn` | ISBN raw (= normalize 前) | `lib/madb-jsonld.ts:52, 405` | `volumes.isbn13` (NFKC normalize 後) |
| `schema:datePublished` | YYYY-MM-DD or partial | `lib/madb-jsonld.ts:53, 439` | `volumes.release_date` + `series.year_started/year_ended` 集計 |
| `schema:name` | localized title (= ja-Hrkt の {@value} で kana 取得) | `lib/madb-jsonld.ts:55, 414` | `volumes` の表示 title / `series.title_kana` |
| `schema:alternateName` | 公式英語題 (= ASCII のみ entry を選択) | `_build-series-v2.py:285` | `series.title_official_en` |
| `schema:alternativeHeadline` | サブタイトル (= "完全版" 等の edition label が入ることあり) | `lib/madb-jsonld.ts:63, 417` | `series.subtitle` / edition label |
| `schema:creator` | 著者 表示文字列 (= "[著]諫山創,スタジオ・ナッツ" 等 role prefix + comma-packed) | `lib/madb-jsonld.ts:57, 432` | `cleanCreatorStrings` で 漢字名 array 化 → mangaka.csv match |
| `schema:brand` | 単行本レーベル (= 漢字 ∥ カナ literal) | `lib/madb-jsonld.ts:58, 436` | `editions.imprint` (= 漢字部分のみ) |
| `schema:publisher` | 発行者名 (= 漢字 ∥ カナ literal) | `lib/madb-jsonld.ts:59, 437` | `series.publisher_key` (= publishers.yml master 解決) |
| `schema:volumeNumber` | 巻番号 表示文字列 (= "13" / "巻ノ五十" / "其之1") | `lib/madb-jsonld.ts:60, 443` | `volumes.number` の **fallback** (= position 不在時のみ) |
| **`schema:position`** | 巻ソート 数値 (= deterministic integer、 仕様 page 72) | `lib/madb-jsonld.ts:61, 446` | **`volumes.number` の primary source** (= commit `bb1786c`) |
| `schema:image` | cover URL (= 1 件目を採用) | `lib/madb-jsonld.ts:62, 447` | `volumes.cover_url` (= ただし MADB 実 data に 0 件、 dead) |
| `schema:identifier` | MADB internal ID (= cluster build 時に使用) | `_build-series-v2.py:282` | record の "madb_id" field |
| **`schema:numberOfItems`** | 総アイテム数 (= MangaBookSeries record の総巻数 候補?) | `_build-series-v2.py:291` | **extract のみ、 dead field** (= cluster の "number_of_items" に保持されるが SQLite 投入 / yaml 出力経路で 未使用) |

### dcterms 系 (= 1 種)

| URI | 用途 | コード位置 | downstream |
|---|---|---|---|
| `dcterms:creator` | 作者 Agent への URI 参照 (= "C53400" 等) | `lib/madb-jsonld.ts:56, 448` | `creatorRefs` で C-ID 抽出 → schema:creator (表示文字列) との pairing 学習に利用 |

---

## 未活用の manga 関連 property (= 仕様書記載、 コード抽出なし)

仕様書 URI list から manga / book / series 関連 と判定したもの。 優先度は **想定される MANGAL での価値** で 主観評価。

### 🔴 HIGH: 巻数 / 完結判定 の direct source

| URI | 推測される意味 | MANGAL での活用案 | 仕様書 確認事項 (= PDF 読破時) |
|---|---|---|---|
| `madb:totalVolumeNumber` | **総巻数** (= 推定 値) | `series.total_volumes` cache column を追加、 promote-bulk の COUNT(*) を 不要に | 適用クラス (= MangaBookSeries で確定？) / 多重度 / 値型 |
| `madb:totalVolumeNumberFinal` | **確定 総巻数** (= 完結後の値) | 完結判定 + 巻数 cache の 決定打 | `totalVolumeNumber` との違い (= 確定 vs 推定?) |
| `madb:volumeNumberFinal` | **最終巻番号** (= 数値) | `series.status = 'completed'` の signal | `schema:position` (= 巻 per-record) との関係 |
| `madb:issueNumberDisplayedFinal` | **最終巻 表示文字列** (= "其之二十三" 等) | 表示用、 数値 + 表示の組合せ | `schema:volumeNumber` (= 巻 per-record) との関係 |
| `madb:datePublishedFinal` | **最終 出版日** | `series.year_ended` の direct source (= 現状 volumes.release_date の MAX 集計) | 多重度 (= 1 or N?) |

### 🟠 MED: 関連作品 / シリーズ間 link

| URI | 推測される意味 | MANGAL での活用案 |
|---|---|---|
| `madb:spinOff` | spinoff 関係 (= → child) | `_promote-bulk-v2.py build_parent_map` の自前推定を 不要に |
| `madb:sequel` / `madb:sequelTo` | 続編 関係 | シリーズ chain 可視化 (= 例: 「タッチ」 → 「H2」 → 「MAJOR」?) |
| `madb:precedes` / `madb:succeeds` | 前後関係 (= シリーズ chain) | 上記同 |
| `madb:variantTitle` / `madb:variation` / `madb:variationOf` | 表記揺れ / variant 関係 | slug rename 不要化、 別表記 候補 |
| `madb:expandedAs` / `madb:localizedAs` / `madb:remadeAs` | 翻訳版 / リメイク 関係 | 「英訳版」 「リブート」 等の 関係性 表示 |
| `madb:embodiment` / `madb:embodimentOf` | 抽象 work と 具体 manifestation の関係 | (= 多分 内部 model 用、 我々は使わない) |

### 🟡 MED: 識別子 / 外部 link

| URI | 推測される意味 | MANGAL での活用案 |
|---|---|---|
| `madb:wikidata` | **Wikidata QID 直 link** | `series.qid` / `mangaka.qid` を NDL/Wikidata 経由 解決から MADB direct に切替 |
| `madb:viaf` | VIAF identifier | 海外 図書館 link |
| `madb:imdb` | IMDb ID | (= アニメ化 link、 多分 AnimationTVProgram にのみ適用) |
| `madb:freebase` | Freebase ID | (= 死んだ DB だが MADB は持ってる) |
| `madb:metacritic` / `madb:mobyGames` | (= VideoGame 専用、 manga 不適用) | — |

### 🟢 MED: 原作 / クレジット詳細

| URI | 推測される意味 | MANGAL での活用案 |
|---|---|---|
| `madb:originalTitle` | 原題 | 翻訳 manga の 原題 表示 |
| `madb:originalWorkName` | 原作 作品名 | コミカライズ の 原作 link |
| `madb:originalWorkCreator` | 原作者 | 共著 role 補完 (= `mangaka.role = 'original_author'`) |
| `madb:originalWorkMedia` | 原作 media 種別 (= 小説 / アニメ / ゲーム) | コミカライズ判定 |
| `madb:wakuTitle` | 「枠 タイトル」 (= 仕様確認要、 シリーズ 集合 title?) | TBD |
| `madb:abbreviatedTitle` | 略称 | 検索 hit 拡張 |

### 🟢 MED: schema.org の manga 適用 候補 (= 仕様書で manga class に適用と確認できれば)

| URI | 推測される意味 | MANGAL での活用案 |
|---|---|---|
| `schema:genre` | ジャンル | 現状 AI fill で genres 補完中、 MADB に元値あれば優先 |
| `schema:numberOfPages` | ページ数 (= per-volume) | `volumes.page_count` 追加 (= 巻ごとの 分量) |
| `schema:isPartOf` | 親 entity link (= MangaBook → MangaBookSeries) | series cluster build の hint (= 現状 _build-series-v2.py の base+creator key で 自前) |
| `schema:hasPart` | 子 entity (= MangaBookSeries → MangaBook) | 上記の inverse |
| `schema:award` | 受賞 | `manga.awards` field の direct source (= 現状 手動 fill) |
| `schema:editor` | 編集者 | クレジット 拡張 |
| `schema:character` | キャラクター | character 検索 (= 大型 feature) |
| `schema:firstAppearance` | 初出 (= character の) | 上記の補完 |
| `schema:copyrightYear` | 著作権年 | `series.year_started` の補強 |
| `schema:copyrightHolder` | 著作権者 | publisher 補強 |
| `schema:keywords` | キーワード | 検索 拡張 (= ジャンル / 設定 tag) |

### ⚪ LOW: 巻 詳細 / 体裁

| URI | 用途 | 備考 |
|---|---|---|
| `madb:format` / `madb:mediaFormat` / `madb:fileType` | フォーマット (= 紙 / 電子) | 電子書籍判定 |
| `madb:price` | 価格 | 過去価格、 現在価格は Amazon に任せる方針 |
| `madb:dataProvider` / `madb:providerIdentifier` / `madb:providerUrl` | 提供元 metadata | 内部 provenance、 我々は使わない |
| `madb:note` / `madb:productionNote` / `madb:publicationNote` | 雑多な note | データ次第 |
| `madb:relatedItem` / `madb:relatedItemName` / `madb:relatedCollection` | 関連物 | データ次第 |

---

## Out-of-scope (= manga 適用外の class 専用)

| URI | 適用 class | 理由 |
|---|---|---|
| `schema:numberOfEpisodes` / `madb:numberOfPrograms` / `schema:actor` / `schema:productionCompany` | AnimationTVProgram | アニメ |
| `schema:gamePlatform` / `madb:porting` / `madb:crossPlay` / `schema:numberOfPlayers` / `madb:metacritic` / `madb:mobyGames` / `madb:twitch` / `schema:operatingSystem` / `schema:softwareVersion` / `schema:availableOnDevice` | VideoGame | ゲーム |
| `madb:eirin` | 映画 (= 映倫) | 映画 |

---

## 仕様書 PDF 読破時の to-do (= 各表に追記する column)

PDF 再 readable 後、 各 property entry に 以下 5 column を追記:

1. **適用クラス** (= MangaBook / MangaBookSeries / MangaMagazine / Agent / Item 等 のどれに 出現するか)
2. **多重度** (= 0..1 / 1 / 0..N / 1..N)
3. **値型** (= literal string / xsd:integer / xsd:date / URI ref / localized literal)
4. **定義 原文** (= 仕様書 page X の 一文)
5. **実 data 出現率** (= MADB metadata104.json / metadata101.json での populated 比率、 PDF と は別軸で .cache/ 復活後に measure)

---

## 関連 commit / file

- `lib/madb-jsonld.ts` (= MangaBook record 抽出、 30+ unit tests in `lib/madb-jsonld.test.ts`)
- `scripts/fetch-madb.ts` (= upsertVolume、 schema:position 採用 commit `bb1786c`)
- `scripts/_build-series-v2.py` (= MangaBookSeries cluster build、 numberOfItems extract)
- `scripts/clean-madb-seed.ts` (= raw seed 整形)
- `scripts/_extract-madb-volume-labels.py` (= volume label 抽出)
- 仕様書 元 repo: `mediaarts-db/dataset` (= 文化庁)
