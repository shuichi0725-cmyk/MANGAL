# MADB JSON-LD field inventory (= 仕様書 vs 現状コード coverage)

> 文化庁 MADB (Media Arts Database) Ver. 1.0 仕様書 (= 2021-03-22、 339 ページ) を
> 直接読破し、 漫画関連 7 classes の全 property を抽出。 現状の MANGAL コードベース
> と cross-reference し、 extract 済 / 部分活用 / 未活用 の 3 status で 分類。
>
> **作成日**: 2026-05-23 (= 初版)、 **更新日**: 2026-05-23 (= PDF 読破後の確定情報で書き直し)
> **base にした仕様書 PDF**: https://github.com/mediaarts-db/dataset/blob/main/doc/MADB%E3%83%A1%E3%82%BF%E3%83%87%E3%83%BC%E3%82%BF%E3%82%B9%E3%82%AD%E3%83%BC%E3%83%9E%E4%BB%95%E6%A7%98%E6%9B%B8%EF%BC%88Ver.1.0%EF%BC%89.pdf
> **読破ページ**: p-27 〜 p-86 (= 漫画関連 7 class の全定義領域)

## クラス階層 (= 仕様書から確定)

```
MangaWork (= 抽象 manga 作品、 仕様 p-27〜p-32)
  上位: Manga, Collection
  URI: class#MangaWork
  ├─ MangaBookSeries (= 単行本シリーズ instance、 p-33〜p-42)
  │   上位: Manga, Collection
  │   URI: class#MangaBookSeries
  │   isPartOf → MangaWork
  │   hasPart → MangaBook
  │   └─ MangaBook (= 単行本 1 冊、 p-58〜p-67)
  │       上位: Manga, Item
  │       URI: class#MangaBook
  │       isPartOf → MangaBookSeries (= "単行本全巻まとめ" 経由)
  └─ MangaMagazinePublication (= 雑誌連載 instance、 p-51〜p-57)
      上位: Manga, Collection
      URI: class#MangaMagazinePublication
      isPartOf → MangaWork

MangaMagazine (= 雑誌全体、 p-43〜p-50)
  上位: Manga, Collection
  URI: class#MangaMagazine
  └─ MangaMagazineVolume (= 雑誌各号、 p-68〜p-77)
      上位: Manga, Item
      URI: class#MangaMagazineVolume
      isPartOf → MangaMagazine (= "雑誌全号まとめ" 経由)

MangaOther (= その他 漫画関連物、 p-78〜p-86)
  上位: Manga, Item
  URI: class#MangaOther
  isPartOf → MangaWork (= "関連作品" 経由)
  定義: 「単行本」「雑誌各号」を除くマンガが掲載された、 もしくはマンガ作品が体現されている出版物や製作物
  例: 同人誌 / 販促冊子 / 貸本短編 (= サブジャンル の値例)
```

## 重要 property のクラス所属マトリクス (= 旧推測の訂正版)

旧 inventory doc では 「volumeNumberFinal は MangaBookSeries」 等を 推測していたが、 **仕様書本文で確定** したので訂正:

| Property URI | 仕様書ラベル | 実適用クラス | 現状コード | MANGAL での価値 |
|---|---|---|---|---|
| **`schema:numberOfItems`** | **マンガ単行本全巻数** (= 整数) | **MangaBookSeries** | `_build-series-v2.py:291` extract のみ、 dead | 🔴 **総巻数 cache の正解 source** |
| **`property/datePublishedFinal`** | **最終巻発行日** (= リテラル) | **MangaBookSeries** (= 「終刊した当該リソースを構成する最新の単行本が発行された日付」)、 + MangaMagazine (= 終刊日) | 未抽出 | 🔴 **完結判定 + year_ended の direct source** |
| `property/volumeNumberFinal` | **終刊号** | **MangaMagazine のみ** | 未抽出 | ⚪ MANGAL 不要 (= 雑誌のみ) |
| `property/totalVolumeNumberFinal` | **終刊通巻号** | **MangaMagazine のみ** | 未抽出 | ⚪ MANGAL 不要 |
| `property/issueNumberDisplayedFinal` | **終刊表示号数** | **MangaMagazine のみ** | 未抽出 | ⚪ MANGAL 不要 |
| `property/issueNumberPublished` | 終刊号 (= 出版上の号) | MangaMagazine のみ | 未抽出 | ⚪ |
| `property/totalVolumeNumber` | **通巻** | **MangaMagazineVolume のみ** (= 各号の通巻番号) | 未抽出 | ⚪ MANGAL 不要 |
| `schema:position` | **巻ソート** (= 連続する巻の順序を示す数値、 10 進数) | **MangaBook** | `lib/madb-jsonld.ts:61, 446` ✅ | ✅ 活用済 (= `volumes.number` primary source、 commit `bb1786c`) |
| `schema:volumeNumber` | **巻** (= 出版における巻次の指定、 整数推奨) | **MangaBook** | `lib/madb-jsonld.ts:60, 443` ✅ | ✅ fallback で活用 |
| `schema:issueNumber` | **号** (= Issue or Number の指定) | **MangaMagazine, MangaMagazineVolume** | 未抽出 | ⚪ MANGAL 不要 |
| `schema:numberOfPages` | **ページ数** | **MangaBook, MangaMagazineVolume** | 未抽出 | 🟡 巻ごとの分量、 詳細表示で有用 |
| `schema:price` | **価格** (= 発行者が設定した希望小売価格) | **MangaBook, MangaMagazineVolume, MangaOther** | 未抽出 | 🟡 出版時 MSRP、 Amazon 価格と並行表示 候補 |
| `property/seriesName` | **シリーズ名** (= 当該リソースが所属するシリーズの名称) | **全 class 共通** | `_build-series-v2.py` 経由で title から推測のみ | 🟡 series cluster build の direct hint |
| `schema:genre` | ジャンル | 全 class 共通、 ただし **値は type 識別子** (= "マンガ作品" / "単行本全巻まとめ" / "雑誌全号まとめ" / "雑誌各号" / "単行本" / "マンガその他") | 未抽出 | ⚪ **コンテンツ ジャンルではない**、 MANGAL の genres 補完には使えない |
| `property/additionalGenre` | **サブジャンル** (= 情報資源分類の下位の分類) | MangaWork / MangaBookSeries / MangaMagazinePublication / MangaBook / MangaMagazineVolume / MangaOther | 未抽出 | 🟡 **MangaOther では「同人誌」「販促冊子」「貸本短編」 の値**。 MangaBookSeries での値域は要 data 検証 (= 真の content genre かは不明) |
| `property/originalWorkCreator` | **原作者名** (= 原作・原案を作成した責任主体の名称) | MangaWork / MangaBookSeries / MangaMagazinePublication / MangaBook / MangaOther | 未抽出 | 🟢 コミカライズ判別、 `original_authors` role の direct source |
| `schema:editor` | **編集人** (= 編集人である個人の名称) | MangaMagazineVolume のみ | 未抽出 | ⚪ 雑誌のみ |
| `schema:contributor` | **スタッフ名** (= 作画やストーリー作成以外で作成に貢献した責任主体、 連載全体に関わる者のみ) | MangaBookSeries / MangaMagazine / MangaMagazinePublication / MangaBook / MangaMagazineVolume / MangaOther | 未抽出 | 🟢 staff credit (= 編集 / アシスタント 等)、 拡張 credit |
| `schema:actor` | **キャスト名** (= 出演したキャストの名称、 マンガ では adapted アニメ等の キャラクター？) | MangaWork / MangaBookSeries / MangaMagazine / MangaMagazinePublication / MangaBook / MangaMagazineVolume | 未抽出 | ⚪ MANGAL では多分 不要 |
| `schema:countryOfOrigin` | **国際地域** (= 統制語彙: 国際地域) | MangaWork / MangaBookSeries / MangaMagazine / MangaMagazinePublication / MangaBook / MangaMagazineVolume / MangaOther | 未抽出 | 🟢 海外漫画判別 (= 日本 以外 が値) |
| `schema:contentRating` | **レイティング** (= 想定される年齢に基づく利用制限) | 全 class 共通 | `lib/madb-jsonld.ts:51, 407` ✅ | ✅ adult filter (= "成年コミック") |
| `schema:image` | **サムネイル** (= 当該リソースの画像) | 全 class 共通 | `lib/madb-jsonld.ts:62, 447` ✅ (= ただし 実 data に 0 件) | dead (= MADB の data 側 0 件) |
| `schema:hasPart` | **関係 (hasPart)** | MangaBookSeries / MangaMagazine | 未抽出 | 🟡 series → 巻 link の direct source (= 現状 序列推定で 自前) |
| `schema:isPartOf` | **マンガ作品 / 単行本全巻まとめ / 雑誌全号まとめ / 関連作品** (= 親 link) | MangaWork 以下全 class | 未抽出 | 🟡 階層構造の direct source (= series cluster build の hint) |
| `property/jpno` | **全国書誌番号** (= 全国書誌番号による識別子) | MangaBookSeries / MangaBook / MangaOther | 未抽出 | 🟢 NDL bibliography ID (= NDL data との突合 hint) |
| `property/binder` | **製本・造本形態** (= 中綴じ / 平綴 / 無線綴 等) | MangaOther | 未抽出 | ⚪ MANGAL 不要 |
| `schema:productID` | **レーベル番号** (= 発行者が定家する型番) | MangaMagazineVolume のみ | 未抽出 | ⚪ |
| `property/seriesNumber` | **シリーズ番号** (= シリーズ内における順序番号) | MangaOther | 未抽出 | ⚪ MangaOther 専用 |
| `property/note` | **備考** | 全 class 共通 | 未抽出 | ⚪ 雑多 |
| `property/ndc` | **分類** (= 日本十進分類法 NDC による分類記号) | MangaBookSeries / MangaBook / MangaMagazineVolume / MangaOther | 未抽出 | ⚪ 図書館分類、 manga genre とは別軸 |

## 現状 extract 済 一覧 (= 17 種、 既存 inventory 表 と同じ)

| URI | コード位置 |
|---|---|
| `@id` (extractMadbId) | `lib/madb-jsonld.ts:401` |
| `@type` | (fixture でのみ確認) |
| `rdfs:label` | `lib/madb-jsonld.ts:50` |
| `schema:contentRating` | `lib/madb-jsonld.ts:51, 407` |
| `schema:description` | `lib/madb-jsonld.ts:54, 411` |
| `schema:isbn` | `lib/madb-jsonld.ts:52, 405` |
| `schema:datePublished` | `lib/madb-jsonld.ts:53, 439` |
| `schema:name` | `lib/madb-jsonld.ts:55, 414` |
| `schema:alternateName` | `_build-series-v2.py:285` |
| `schema:alternativeHeadline` | `lib/madb-jsonld.ts:63, 417` |
| `schema:creator` | `lib/madb-jsonld.ts:57, 432` |
| `schema:brand` | `lib/madb-jsonld.ts:58, 436` |
| `schema:publisher` | `lib/madb-jsonld.ts:59, 437` |
| `schema:volumeNumber` | `lib/madb-jsonld.ts:60, 443` |
| `schema:position` | `lib/madb-jsonld.ts:61, 446` |
| `schema:image` | `lib/madb-jsonld.ts:62, 447` |
| `schema:identifier` | `_build-series-v2.py:282` |
| `schema:numberOfItems` | `_build-series-v2.py:291` (= dead, downstream 未配線) |
| `dcterms:creator` | `lib/madb-jsonld.ts:56, 448` |

## 未活用 property の取込優先順位 (= 仕様書 確定後の更新版)

### 🔴 HIGH (= 単行本 series の core info)

1. **`schema:numberOfItems` を downstream に配線** (= 既 extract、 dead)
   - 対象: MangaBookSeries record
   - 配線先: 種2 schema に `series.total_volumes_madb INTEGER` 追加 → `_populate-v2.py` で 投入
   - 効果: promote-bulk-v2 が 巻数 を `COUNT(*) FROM volumes` でなく direct read 可能、 「全 X 巻」 表示が正確に

2. **`property/datePublishedFinal` を extract + 配線**
   - 対象: MangaBookSeries record
   - 配線先: 種2 schema に `series.date_published_final TEXT` 追加 (= or 既存 `year_ended` で 代替)
   - 効果: 完結 manga の `year_ended` が 確定値 に、 status='completed' の判定 が 仕様 由来

### 🟡 MED (= 補助 info)

3. **`schema:isPartOf` / `schema:hasPart` 取込**
   - MangaBook → MangaBookSeries の direct link (= 現状 base+creator key で 自前 cluster build)
   - 効果: cluster 分裂 (= 「鬼平犯科帳」 4 cluster 等) の根本解決の hint

4. **`property/originalWorkCreator` 取込**
   - 対象: 全 class
   - 配線: `series_authors.role = 'original_author'` の direct source
   - 効果: 共著 role の AI 推定不要

5. **`property/seriesName` 取込**
   - 対象: 全 class (= 多 lang variant 含む)
   - 配線: series cluster の `series_name` field、 現状の base title 推測の補強

6. **`schema:numberOfPages` 取込**
   - 対象: MangaBook
   - 配線: `volumes.page_count INTEGER` 追加
   - 効果: 巻 detail の 分量 表示

7. **`schema:price` 取込**
   - 対象: MangaBook
   - 配線: `volumes.price_msrp INTEGER` 追加 (= 既存 `volumes.price` と区別)
   - 効果: 発売時 MSRP の保持、 Amazon 価格 と並行 表示

8. **`property/jpno` 取込**
   - 対象: MangaBookSeries / MangaBook
   - 配線: `series.jpno TEXT` / `volumes.jpno TEXT`
   - 効果: NDL data との突合 ID

### 🟢 LOW (= future / 検証要)

9. **`property/additionalGenre` 値域 検証**
   - MangaOther では "同人誌" 等の type、 MangaBookSeries では 何が入るか **実 data 確認要**
   - もし 真の content genre なら AI fill 廃止可能

10. **`schema:countryOfOrigin` 取込**
    - 海外 manga (= 日本 以外) を 別ライン 扱いするための signal

## 期待される改善 (= 上位 1-2 を導入した場合)

- `_promote-bulk-v2.py` で `n_isbn = COUNT(*) FROM volumes` が `total_volumes_madb` の direct read に
- `series.year_ended` の AI fill / volumes.release_date MAX 集計 が `date_published_final` の direct read に
- `_promote-bulk-v2.py build_parent_map` の自前推定 (= n_isbn 比較 で 親子) が **不要 or 補強** される (= hasPart の有無で 確実)
- 種3 v2 の AI fill 不要 field が 2 種 増加 (= total_volumes と year_ended 系)

## Out-of-scope (= MANGAL では使わない)

| URI | 適用クラス | 理由 |
|---|---|---|
| volumeNumberFinal / issueNumberDisplayedFinal / totalVolumeNumberFinal / issueNumberPublished | MangaMagazine | MANGAL は雑誌 表示しない |
| totalVolumeNumber | MangaMagazineVolume | 同上 |
| publicationPeriodicity (= 発行頻度) | MangaMagazine | 同上 |
| binder (= 製本形態) | MangaOther | 関連書扱いで弾く |
| schema:editor (= 編集人) | MangaMagazineVolume | 同上 |
| eirin (= 映倫) | 映画 | manga 不適用 |
| 各 schema.org video/game/animation 系 | AnimationTVProgram / VideoGame | 別 entity |

## 関連 commit / file

- `lib/madb-jsonld.ts` (= MangaBook record 抽出、 30+ unit tests in `lib/madb-jsonld.test.ts`)
- `scripts/fetch-madb.ts` (= upsertVolume、 schema:position 採用 commit `bb1786c`)
- `scripts/_build-series-v2.py` (= MangaBookSeries cluster build、 numberOfItems extract のみ・ dead)
- `scripts/clean-madb-seed.ts` (= raw seed 整形)
- `scripts/_extract-madb-volume-labels.py` (= volume label 抽出)
- 仕様書 元 repo: `mediaarts-db/dataset` (= 文化庁)
- 関連 inventory memory: [[madb-spec-review-pending]] (= 再開手順)
