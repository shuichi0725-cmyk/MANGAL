# MANGAL ロードマップ

このドキュメントは、データベースの自動構築可能性と、多言語化の方針をまとめたもの。実装はしておらず、判断材料・着手手順の整理のみ。

---

# データベース自動構築の実現可能性

## Context
ユーザの目的は「日本の漫画」の網羅的なカタログ。現状は YAML 20件分の手書きシードのみ。「今すぐ作るわけではないが、自動でどこまで作れるかのメドを知りたい」というのが今回のリクエスト。

ここでは **どのデータが自動で取れて、どのデータが人手必須か** を整理し、本格スケールに進む時に必要な実装と所要を見積もる。実装には着手しない。

## 結論ファースト

| 項目 | 自動化レベル | ソース |
|---|---|---|
| タイトル / よみがな | ◎ 完全自動 | Wikidata + openBD |
| 著者 / 原作者 | ◎ 完全自動 | Wikidata |
| 連載開始年 / 終了年 / status | ◯ ほぼ自動（80〜90%） | Wikidata |
| 出版社 | ◯ ほぼ自動 | Wikidata |
| 連載誌 | △ 50〜70%（メジャー誌は◯、マイナーは×） | Wikidata |
| 分野（少年／青年／少女／…） | △ 連載誌から自動推定可（70%） | `data/magazines.yml` のデモグラ参照 |
| **ジャンル（ギャグ/ラブコメ/…）** | × 手動か、半自動（synopsis から辞書推定） | Wikidata の分類は粗くて使い物にならない |
| あらすじ | △ Wikipedia 概要から抜粋可（要要約処理） | Wikipedia API（CC BY-SA、出典明示必須） |
| 各巻 ISBN | ◯ Wikidata 検索 + openBD 補完 | Wikidata + openBD |
| 各巻 表紙 / 発売日 | ◎ ISBN さえあれば openBD で完全自動 | openBD |

**現実的な上限：人手1〜2週で 5,000 件規模のカタログは到達可能。完全 10,000 件 + 高品質ジャンルは1人だと半年スケール。**

## 各データソースの実態

### openBD（無料、認証不要、再配布可）
- ISBN を渡すと書誌（タイトル／著者／出版社／発売日／表紙URL）が返る
- 1リクエストで 100〜1000 ISBN まとめて取得可
- ISBN付きで日本国内に流通したコミックス単行本はほぼ全網羅
- **弱点**: 「シリーズ」概念がない。1冊=1レコードなので同シリーズの巻をまとめる仕組みは別途必要
- 既存の `scripts/fetch-volumes.ts` がここを叩いている

### Wikidata SPARQL（無料、認証不要、CC0）
- `wd:Q8274 (manga)` インスタンスで日本国 P495=Q17 の作品を全検索可
- 連載開始日 P580、終了日 P582、著者 P50、出版社 P123、連載誌 P1433 などが構造化済み
- 期待ヒット数：5,000〜10,000（Wikipedia 記事のある作品にほぼ等しい）
- **弱点**: ジャンル分類は P136 にあるが「アクション」「冒険」など粗いラベルが混在し、サイトのジャンル定義と一致させにくい
- クエリ例（タイトル/著者/出版社/連載開始年）:
  ```sparql
  SELECT ?manga ?titleJa ?author ?publisher ?magazine ?yearStarted ?yearEnded WHERE {
    ?manga wdt:P31 wd:Q8274 ;
           wdt:P495 wd:Q17 .
    OPTIONAL { ?manga rdfs:label ?titleJa FILTER(LANG(?titleJa)="ja") }
    OPTIONAL { ?manga wdt:P50 ?authorItem . ?authorItem rdfs:label ?author FILTER(LANG(?author)="ja") }
    OPTIONAL { ?manga wdt:P123 ?publisherItem . ?publisherItem rdfs:label ?publisher FILTER(LANG(?publisher)="ja") }
    OPTIONAL { ?manga wdt:P1433 ?magazineItem . ?magazineItem rdfs:label ?magazine FILTER(LANG(?magazine)="ja") }
    OPTIONAL { ?manga wdt:P580 ?yearStarted . }
    OPTIONAL { ?manga wdt:P582 ?yearEnded . }
  }
  LIMIT 5000
  ```

### Wikipedia 概要（CC BY-SA、帰属必須）
- REST API で記事冒頭の "extract" を取得可
- 200〜500字のあらすじとして使える
- **注意**: 出典表記をフッター等に明示する必要

### Amazon PA-API（要承認、3件成約後）
- 商品メタ + 公式表紙画像
- ジャンルは「Amazon内のカテゴリ」で粗いがあるにはある
- 承認まで使えないのでフェーズBの位置付け

## 自動化スクリプトの構想（実装しない）

実装する場合に必要となるスクリプト群：

| スクリプト | 役割 | 想定行数 | 工数 |
|---|---|---|---|
| `scripts/import-wikidata.ts` | SPARQL → 5000件規模の YAML 雛形生成。`title / kana / authors / publisher / magazine / year_started / year_ended / status` を埋める | ~250 | 1日 |
| `scripts/infer-demographics.ts` | 既存 `data/magazines.yml` の magazine→demographic マッピングを用いて分野を自動推定 | ~50 | 半日 |
| `scripts/infer-genres.ts` | キーワード辞書（"バスケ"→sports, "刑事"→mystery, "魔法"→fantasy など）で synopsis からジャンル候補を吐く。確信度付き | ~150 | 1日 |
| `scripts/genre-tagging-ui/` | ローカル開発専用のジャンル付与 GUI（一覧 → ワンクリックでチップ追加 → YAML 上書き）。Next.js のサブルートでも可 | ~300 | 2日 |
| `scripts/fetch-wiki-synopsis.ts` | Wikipedia REST API であらすじ取得＋出典格納 | ~80 | 半日 |
| `scripts/normalize-and-dedupe.ts` | タイトル正規化、スラッグ衝突回避、4コマ／同人除外フィルタ | ~150 | 1日 |
| `scripts/fetch-volume-isbns.ts` | Wikidata の P212（ISBN-13）か、楽天ブックスの「シリーズ検索」で各巻 ISBN を集める | ~200 | 1〜2日 |
| `scripts/yaml-to-sqlite.ts`（任意） | 1000本超で Turso 移行する場合の同期スクリプト | ~100 | 半日 |

合計: **約 1500 行 / 7〜10 日分の作業**で「Wikidata 取得 → 自動付与 → 半自動ジャンル付与 → 巻ISBN 取得 → 表紙/発売日 一括」のパイプラインが揃う。

## 想定タイムライン（実装する場合）

| フェーズ | 期間 | 出来上がり |
|---|---|---|
| Stage 1: Wikidata import | 1日 | 5,000件分の YAML 雛形（タイトル/著者/年/出版社が埋まった状態、ジャンル空） |
| Stage 2: 分野自動推定 | 半日 | demographic が 70% 自動充足 |
| Stage 3: ジャンル半自動付与 | 2〜3日 | 辞書推定 + GUI クリック付与で全件にジャンル |
| Stage 4: あらすじ流し込み | 半日 | Wikipedia から抜粋 + 出典 |
| Stage 5: 正規化・除外 | 1〜2日 | 重複・対象外作品（4コマ・同人）の整理 |
| Stage 6: 巻別 ISBN 自動取得 | 1〜2日 | 各巻 ISBN → openBD で表紙/発売日まで一括投入 |
| **合計** | **1〜2週間** | **5,000 件規模の本格カタログ** |

## 既存の足回りで使えるもの

- `lib/schema.ts`: Zod スキーマがあるので、自動生成された YAML もそのまま検証してビルド時にハネられる
- `lib/loadData.ts`: 5,000 件の YAML 読み込みも問題ない（一回のビルド時 I/O）
- `scripts/fetch-volumes.ts`: ISBN リストを渡せば openBD から表紙/発売日を一括補完できる既存実装
- `scripts/fetch-openbd.ts`: 単発書誌取得（雛形生成用）

これらは **そのまま再利用できる** ので、追加実装は前述の 6〜8 本のスクリプトのみ。

## 落とし穴

1. **ジャンル分類体系を最初に固める必要**: 「アクション/冒険/バトル」「ラブコメ/恋愛」みたいな境界を後から動かすと全件再分類になる
2. **Wikidata の網羅性は「人気作品 = 高、マイナー作品 = 低」**: 連載誌が空のレコードがそれなりに出る
3. **連載中作品の更新追従**: 最新巻が出た時の ISBN 追加は手動 or cron 化が必要
4. **権利**: openBD のカバー、Wikidata は問題なし。Wikipedia 抜粋は CC BY-SA で出典必須。Amazon 画像は PA-API 経由のみ可
5. **規模が 1万件超になったら**: YAML より SQLite/Turso の方が編集しやすい。それまでは YAML で十分

## 結論

- **「タイトル/著者/出版社/年/連載誌」だけなら 5,000 件を 1 日で自動投入可能**
- **「分野」は連載誌マッピングで 70% 自動**
- **「ジャンル」だけが本気の手作業（あるいは半自動 UI 必須）**
- 全自動 100% は現実的でないが、**人間1人で1〜2週間あれば 5,000件級** は十分到達可能

着手したくなったタイミングで `scripts/import-wikidata.ts` から始めるのが最短ルート。MVP の実装と既存スクリプトはそのまま使える。

---

# 楽天ブックスAPI による大規模データ取得（推奨パイプライン）

Wikidata のマンガ作品インスタンスより、**「漫画家リスト × 楽天ブックスAPI」** の方が網羅性・鮮度ともに上回る。実装する場合の本命ルート。

## API 概要

- **正式名**: 楽天ブックス書籍検索API
- **エンドポイント**: `https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404`
- **認証**: `applicationId` 必須。https://webservice.rakuten.co.jp/ で無料取得（メール登録のみ）
- **レート制限**: 1 req/sec / アプリID
- **ページング**: 1ページ最大30件、最大100ページ＝1検索クエリで最大3,000件
- **商用利用**: 可。「Powered by 楽天ウェブサービス」のクレジット表示が必須

### 取得できるフィールド

| フィールド | 中身 |
|---|---|
| `title` | 書籍タイトル |
| `titleKana` | よみがな |
| `author` / `authorKana` | 著者 |
| `publisherName` | 出版社 |
| `salesDate` | 発売日（"YYYY年MM月DD日" 文字列） |
| `isbn` | ISBN-13 |
| `largeImageUrl` / `mediumImageUrl` / `smallImageUrl` | 楽天 CDN の表紙画像 |
| `itemCaption` | 商品説明（あらすじ素材として利用可） |
| `seriesName` / `seriesNameKana` | シリーズ名（巻集約のキー） |
| `booksGenreId` | 楽天ジャンルID（成年向け除外フィルタの基幹） |

## openBD・Wikidata との比較

| 観点 | openBD | Wikidata | **楽天ブックス API** |
|---|---|---|---|
| 認証 | 不要 | 不要 | アプリID登録（無料・即時） |
| ISBN 無しでシリーズ全巻取得 | ✗ | △ | **◎** タイトル+著者で全巻一発 |
| 表紙画像のカバー率 | 一部欠 | なし | **◎** 古い本でもカバー率高い |
| 発売日 | あり（YYYYMMDD） | あり | あり（要パース） |
| あらすじ | なし | × | △（itemCaption） |
| ジャンル | なし | △（粗い） | △（楽天カテゴリ、成人向け識別に有用） |
| 商用利用 | 可・再配布可 | CC0 | 可・クレジット必須 |

## 推奨パイプライン: Wikipedia(漫画家) × 楽天ブックス

```
[Wikidata SPARQL]
  occupation = mangaka, citizenship = Japan
  → mangaka_list.csv（約 6,000〜8,000 人）

  ↓

[楽天ブックスAPI ループ]
  for each mangaka:
    GET ?author=<名前>&booksGenreId=<少年/青年/少女/女性のいずれか>
    pagination で全件取得

  ↓

[シリーズ集約]
  group by seriesName (空ならタイトル正規化キー)
  → 約 20,000〜30,000 シリーズ候補

  ↓

[エディション重複排除・正規化]
  「ジャンプ・コミックス」「文庫版」「完全版」の論理統合
  → 約 12,000〜20,000 ユニーク本作

  ↓

[YAML 雛形生成]
  data/manga/<slug>.yml （volumes[] が発売日順で自動構築）

  ↓

[手動: ジャンル付与・分野確認]
  半自動 UI で2〜5日 / 1000件あたり
```

## 規模見積もり

- 商業出版された主要シリーズの **8〜9割** を機械的にカバー
- 1晩バッチ（楽天 API 1 req/sec で約6時間）で全クロール完了
- スクリプト3本で 約4日 + ジャンル付け数日 = **2週間で 15,000シリーズ規模の本格カタログ**

## ⚠️ 【必須】成年向けコンテンツの除外

**Amazon アソシエイト・プログラム運営規約により、成年向け（18禁/R-18/わいせつ・ポルノ表現）を含むサイトは申請却下・アカウント永久停止の対象**。本サイトの存続要件。

> サイトには、わいせつ、ポルノ、性的な、嫌がらせ、暴力的な、人種差別的な、攻撃的な、または信用を傷つける情報、表現、画像を一切含むことができません。  
> （Amazon.co.jp アソシエイト・プログラム運営規約より要約）

### 多層フィルタ戦略（全層必須）

| 層 | 対策 | 実装場所 |
|---|---|---|
| **1. 楽天ジャンルIDホワイトリスト** | `booksGenreId` を「少年/青年/少女/女性コミック」のみに限定。成年向けジャンルIDは取得対象から完全除外 | API リクエストパラメータ |
| **2. キーワード正規表現** | タイトル・itemCaption に `成年向け` `R-18` `18禁` `アダルト` `官能` `成人指定` 等が含まれたら即除外 | 取得後フィルタ |
| **3. 出版社ブラックリスト** | 茜新社・コアマガジン・ティーアイネット・ワニマガジン社・ヒット出版社・ジーオーティー等を一律スキップ。竹書房等の混在出版社は手動レビューに回す | 取得後フィルタ |
| **4. 作者の Wikidata クロスチェック** | `wdt:P136 wd:Q172241` (genre: hentai) の作品が紐づく作家は最初から候補リストから除外 | SPARQL 段階 |
| **5. 手動レビューゲート** | グレー判定 (`adult_confidence: 0.3〜0.8`) は `.cache/review-queue.jsonl` に出して人手で採否決定。直接 `data/manga/` に書かない | 取得後フィルタ |

### スキーマ方針

`lib/schema.ts` の `Demographic` enum に **`adult` を追加しない**。混入したものは「その他」ではなく **削除** が方針。データに残すと将来の混入リスクになる。

### 同人・周辺カテゴリの扱い

- **同人誌**（COMIC ZIN、メロンブックス、虎の穴等の同人レーベル）は最初から対象外
- **TL（ティーンズラブ）**: 一般向けと18禁が混在 → レーベル単位で手動レビュー
- **BL**: 一般向けはOK、ただし商業誌でも18禁レーベルあり → レーベル単位でレビュー
- **ハーレクインコミック**: 楽天で R18 扱いが多い → デフォルト除外

### 楽天アフィリエイトとの違い

楽天アフィリエイトは成年向けに比較的寛容だが、**Amazon の基準で判断する**（Amazon の方が厳しい）。楽天 API のジャンル分類を流用すれば、成人向けの線引きはむしろ Amazon より明確に切れる。

## 自動化スクリプト構想（一部実装済み）

| スクリプト | 役割 | 想定行数 | 工数 | 状態 |
|---|---|---|---|---|
| `scripts/fetch-mangaka.ts` | Wikidata SPARQL → 漫画家リスト CSV（hentai クレジット作家を `has_adult_credit=true` でフラグ） | ~140 | 1日 | **実装済み** |
| `scripts/fetch-rakuten.ts` | 単発: タイトル+作家指定で楽天検索 → エディション分類済み YAML 草稿。成年向けジャンル除外 | ~440 | 1.5日 | **実装済み** |
| `scripts/fetch-rakuten-bulk.ts` | 一括: mangaka.csv の全作家を楽天 API でクロールし `.cache/rakuten/<qid>.json` に保存。resume 対応・1.1s スリープ | ~270 | 1日 | **実装済み** |
| `scripts/group-into-series.ts` | キャッシュ JSON をシリーズキー（seriesName / 正規化タイトル）で集約し `data/manga/_drafts/<slug>.yml` を吐く | ~340 | 1.5日 | **実装済み** |
| `scripts/review-queue-cli.ts` | グレー判定の手動採否ツール | ~100 | 半日 | 未着手 |

合計 約700行・4〜5日 + 手作業ジャンル付け数日。

## 環境変数

`.env.example` に以下を追加:
```
RAKUTEN_APP_ID=
```

---

## 多言語化の方針（SEO + アフィリエイト収益の観点）

### 結論

| 言語 | 対応 | 理由 |
|---|---|---|
| 日本語 | 必須（現状） | メイン市場 amazon.co.jp |
| 英語 | フェーズ2 | 検索ボリューム世界一、amazon.com / .co.uk |
| **フランス語** | フェーズ2〜3 | 漫画売上 世界2位、amazon.fr で収益化可能 |
| ドイツ語 | フェーズ3 | amazon.de + 安定した二次市場 |
| スペイン語 | フェーズ4以降 | 中南米含めて広いが分散 |
| ポルトガル語(BR) | フェーズ4以降 | 大市場だが amazon.com.br アソシエイト要確認 |
| イタリア語 | 検討 | 出版数多いが検索流入は中規模 |
| **中国語（簡/繁）** | **やらない** | amazon.cn 撤退済み・収益動線なし。SEO 流入はあっても収益化できないため対象外 |
| 韓国語 | やらない | 同上、Amazon 収益動線が弱い |

### フランス語を入れる根拠
- フランスは日本に次ぐ世界2位の漫画市場（書籍漫画売上）
- amazon.fr アソシエイト規約は日本と同等
- フランス語タイトル（例: 進撃の巨人 → *L'Attaque des Titans*）で検索する読者を取り込める＝日本語サイトでは取れない流入
- Wikidata の `rdfs:label@fr` で公式仏語タイトルが自動取得可

### 技術的な実装パス（参考）

1. **Next.js i18n routing** — `/`（ja default）、`/en/...`、`/fr/...`、`/de/...`
2. **スキーマ拡張** — 各 YAML に翻訳フィールドを追加
   ```yaml
   title: ONE PIECE
   title_translations: { en: One Piece, fr: One Piece, de: One Piece }
   synopsis_translations: { en: "...", fr: "..." }
   ```
3. **翻訳の自動取得**
   - タイトル: Wikidata の各言語ラベル（`@en` `@fr` `@de`）→ ほぼ自動
   - あらすじ: Wikipedia 各言語版抜粋（CC BY-SA、出典明示必須） or DeepL/Google Translate API
   - ジャンル・分野マスタ: 言語数 × 約25キー = 100件程度の固定翻訳テーブル（手動で一度作れば終わり）
4. **Amazon ストア切替** — `lib/amazon.ts` の `LOCALE_DOMAIN` に `fr: amazon.fr`、`de: amazon.de` などを追加
5. **言語別アソシエイトタグ** — 各国 Amazon で別々にアソシエイト登録が必要（タグも国別、3件成約縛りも国別）

### 工数感

| 作業 | 工数 |
|---|---|
| Next.js i18n 配線 | 1日 |
| スキーマ＋ローダ拡張 | 半日 |
| 翻訳取得スクリプト（Wikidata + Wikipedia 抜粋） | 1日 |
| ジャンル等マスタ翻訳（手動） | 半日（言語あたり） |
| 各国Amazonアソシエイト登録 | 各国独立、審査込みで数日〜数週 |

### 推奨ロードマップ

1. 現在: 日本語のみで形を固める → 日本でアソシエイト3件成約
2. 日本での収益が立ち上がったら **英語版** を追加（amazon.com 連携）
3. 英語版が回り始めたら **フランス語版**（ROI が最も高い二次言語）
4. 市場反応を見ながら **ドイツ語 → スペイン語** の順で拡張

中国語・韓国語は対応しない。アジア圏は別エコシステムが強く、Amazon アフィリエイト型のサイトとしては投資効率が合わない。
