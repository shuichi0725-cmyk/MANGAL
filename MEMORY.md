# MANGAL Project Memory

> このファイルは Claude Code session の context bootstrap 用。新しいセッションを開始したら最初に読むこと。

最終更新: 2026-05-08

## プロジェクト概要

- 漫画作品の Japanese database (NDL Search ベース) + Next.js 静的 export frontend
- 最終ターゲット: Amazon アフィリエイトサイト
- 戦略原則: **Amazon カバー画像 / 価格 / 在庫のみ使用**。NDL/openBD/Rakuten 等の画像・価格は不使用 (Phase 5 で PA-API 承認後に Amazon に切替)
- 現在 Phase 4.5 相当 (DB 整備 + bulk-promote pipeline + frontend MVP + CI auto-deploy 完成)、 Phase 5 = Amazon PA-API 承認待ち

## 主要ファイル

### Backend / DB / pipeline
- `db/schema.sql`: 現行 schema_version = 6 (5 → 6: adult_imprints 追加 [Tier 2])
- `scripts/promote-bulk.ts`: NDL → series/editions 自動 promote。adult 検出は `lib/adult-score.ts` 経由
- `scripts/promote-drafts.ts`: `_drafts/*.yml` のうち placeholder 0 件のものを `data/manga/*.yml` へ昇格
- `lib/adult-score.ts`: `computeAdultScore` の純関数実装 + unit test (`lib/adult-score.test.ts`)
- `lib/adult-imprints.ts`: `data/seeds/adult-imprints.yml` の Zod schema + reader
- `lib/openbd-kana.ts`: openBD collationkey (= ヨミガナ katakana) → hiragana 変換ヘルパ + tests
- `scripts/fetch-adult-lists.ts`: JA Wikipedia から adult publishers / mangaka リスト取得 (Fix C)
- `scripts/seed-adult-imprints.ts`: yaml seed → adult_imprints テーブル INSERT (Tier 2)
- `scripts/clean-imprint-dump.ts`: raw imprint dump → adult-imprints.yml 生成 (Tier 2)
- `scripts/fetch-ndl.ts`, `scripts/fetch-wikidata.ts`: 既存の主要 fetcher
- `scripts/fetch-wikipedia.ts`: layer A/B/C diagnostic 入り、 magazine/genre/synopsis/kana 補完
- `scripts/fetch-openbd-bulk.ts`: title_kana のみ openBD で補完 (66% カバレッジ)
- `scripts/probe-openbd.ts`: openBD coverage 測定 (read-only diagnostic)
- `lib/edition.ts`: `normalizeCreatorName`, `matchAdultPublisher` 等の utility
- `data/seeds/_raw-imprint-dump.txt`: ユーザ提示の raw imprint→publisher dump (~339 entry)
- `data/seeds/adult-imprints.yml`: 整形済 adult imprint seed (252 imprints + 14 distribution_channels + 13 ambiguous)
- `data/seeds/adult-publishers-manual.yml`: 白夜書房等の manual seed (Wikipedia 抽出に出ない補完)

### Frontend (Next.js 15.5.15 + Tailwind 4.2.4)
- `app/HomeClient.tsx`: ホーム (Search + CategoryHub + FilterPanel + MangaGrid)
- `app/manga/[slug]/page.tsx`: 詳細ページ (cover slot / メタ / synopsis / 受賞歴 / VolumeRow / Wikidata link)
- `components/CategoryHub.tsx`: ホーム top の 12 タイル grid (種類 4 + 分野 4 + 並び順 4)
- `components/MangaCard.tsx`, `MangaGrid.tsx`: ホーム 1 列縦リスト
- `components/VolumeTile.tsx`, `VolumeRow.tsx`: 巻一覧 (横並び flex、 cover slot 左 / メタ右)
- `components/FilterPanel.tsx`: 種類 / 連載状態 / 並び順 / 出版年 / 出版社 / 連載誌 / 著者 / ジャンル
- `components/CoverImage.tsx`: src=null 時 null 返却 (= placeholder 廃止、 親側で conditional 描画)
- `components/SearchBox.tsx`, `AffiliateLink.tsx`
- `lib/loadData.ts`: `loadAllManga()` で yaml + master を全件 load
- `lib/schema.ts`: MangaSchema (title_kana / authors / publisher / magazine / demographic / genres / synopsis / **anime_adapted / anime_first_year / alternative_titles / awards / wikidata_qid** / editions). VolumeSchema に **kindle_asin / description** 追加。 schema 拡張は全 optional (= 既存 yaml 不変で互換)
- `lib/filters.ts`: FilterState (query, yearMin/Max, demographics, publishers, magazines, authors, genres, **anime, hasAwards, statuses, sort**) + applyFilters + sortItems + filtersFromSearchParams (URL → state、 URL = source of truth)
- `lib/format.ts`, `lib/romaji.ts`, `lib/kana.ts`: format / 表記変換 utility
- `wrangler.jsonc`: Cloudflare Workers Assets で `out/` を配信
- `next.config.ts`: `output: "export"` 静的生成、 `unoptimized: true`

### Workflows
- `.github/workflows/bulk-promote-test.yml`: NDL fetch → wikipedia → openbd:bulk → promote → drafts quality stats → upload artifact
- `.github/workflows/deploy-cloudflare.yml`: push trigger で Next build → wrangler deploy (= CI auto-deploy、 必要 secrets: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID)

## 現在の adult 検出設計 (Fix C + Tier 1B/2, 2026-05 完成)

`lib/adult-score.ts` の `computeAdultScore` (純関数。 unit test は `lib/adult-score.test.ts` に 27 ケース) が 4 signal を additive 合算 (threshold = 3 で skip):

| Signal | Source | Weight |
|---|---|---|
| `wikidata_hentai_credit` | mangaka.has_adult_credit (Wikidata P136=Q172241) | +2 |
| `wikipedia_adult_mangaka_list` | adult_mangaka_known テーブル (Wikipedia「日本の成人向け漫画家の一覧」) | +2 |
| `adult_imprint` | adult_imprints テーブル (manga-db.com 系 dump、 252 imprint、 Tier 2) | +3 |
| `adult_publisher_imprint` | adult_publishers テーブル (Wikipedia「成人向け漫画雑誌の一覧」+ manual seed) | +3 |

Option B 設計: 作家シグナルのみ (2 or 4) では threshold に届かない/届くで線を引き、出版社/imprint シグナル (+3) は単独で確定とする。
imprint と publisher は **排他** (どちらか一方だけ発火、 imprint の方が granular なので優先)。
**`adult_score >= 3` で promote-bulk が draft skip**。試金石 run #11 (qids=Q193300 Q1121064) で:

- 唯登詩樹 ジャンクション/Uma・uma (白夜書房) → score=5 → skip ✅
- 唯登詩樹 集英社/講談社 一般作品 (Kirara, Yui shop, ボクのふたつの翼 等) → score=2 → drafted ✅
- 手塚治虫 全 13 シリーズ → score=0 → drafted ✅

`adult_publishers` は精選 21 件 (五十音/ノイズ/「○○書店」等を除外)。
Tier 1B (2026-05-06) で大手 mainstream publisher (講談社・白泉社・集英社・小学館・秋田書店・KADOKAWA・芳文社・実業之日本社・少年画報社・ぶんか社 等 22 社) を `PUBLISHER_DENY_LIST` に追加。

## 試金石 (canary) 作家

- **Q193300 = 手塚治虫**: 一般中心。false positive 検出用
- **Q1121064 = 唯登詩樹**: adult/general 混在型。mixed-portfolio 検出用 (難ケース)
- **scaling-sample-50** (`data/seed/scaling-sample-50.txt`, 2026-05-05): 6,752 名 CSV から stride 135 で 50 名 sample。 GH Actions run #25389566324 (8 分 29 秒、緑、 599 series → 233 drafts)

## scaling-sample-50 で判明した知見 (2026-05-05)

### 解消済み (Tier 1A)

- **「きい」(Q38276629) false positive**: Wikipedia 「日本の成人向け漫画家の一覧」の短名 「きい」 が我々の DB の 堀田きいち (別名「きい」) と normalize 後一致し、 君と僕。@ Square Enix Gangan を始め全 50+ シリーズに `wikipedia_adult_mangaka_list=2` を誤発火させていた (Option B のおかげで score=2 < 3 で drafted されており実害なしだが、 review 時 misleading)
- **対処**: `scripts/fetch-adult-lists.ts` の `extractAdultMangaka` で normalized 後 length < 3 を弾くよう変更。 publisher 側 (line 200) は元から `< 2` フィルタあり、これで mangaka 側も対称化。 1-2 文字の legitimate な adult-only 作家がいた場合は将来的に `data/seeds/adult-mangaka-supplement.yml` (未作成) で手動救済する前提

### 解消済み (Tier 1B + Tier 2, 2026-05-06)

- **倉科遼 / 氏賀Y太 などの adult-leaning 作家の false-negative**:
  - 原因: publisher 単位 (リイド社・辰巳出版・ぶんか社等) では adult/mainstream 二値判定不能、 真の granularity は imprint 単位 (例: クリベロン@リイド社、 ペンギンクラブ@辰巳出版、 サイベリア系@ぶんか社)
  - **対処 Tier 2**: ユーザ提示の imprint→publisher dump (~339 entry、 manga-db.com 系) を整形して 252 imprint を `data/seeds/adult-imprints.yml` に seed、 新テーブル `adult_imprints` + 新シグナル `adult_imprint` (+3) を `computeAdultScore` に追加。 imprint 単位 (granular) と publisher 単位 (coarse) は排他で発火
  - **対処 Tier 1B**: dump にゼロ件 / 0.x% 程度の大手 mainstream publisher (講談社・白泉社・集英社・小学館・秋田書店・KADOKAWA・芳文社・実業之日本社・少年画報社・ぶんか社 等 22 社) を `PUBLISHER_DENY_LIST` に追加、 publisher 単位 false-positive を抑制
  - 排他 collision (アクションコミックス: 双葉社 mainstream + 双葉社（アクションピザッツ） adult 両方共有) は `ambiguous` セクションに分離して seed には入れない (false-positive 防止)。 13 entry が ambiguous、 14 entry が distribution_channels (DLwolf18 系)

### 未解消 (将来)

- **3A (Phase 5)**: Amazon PA-API BrowseNode による direct 判定 (`amazon_metadata.is_adult_browse_node` 経由) — PA-API 承認後

## 未解決の課題 / 観察

- 唯登詩樹の成年コミックの大多数 (adultcomic.dbsearch.net 上で確認可能) は NDL に integration 漏れ → 我々の DB にも未収録
- これは出典 (NDL) の特性。アフィリエイト戦略上は**成年コミックを掲載しない**方針なので実害は無いが、false-negative 検出 (adult_mangaka_known/adult_publishers いずれにも未該当だが NDL には掲載) のリスクは残る

## 検討した追加データソース案 (2026-05-05 セッション)

### 案 A. openBD 全件 dump → 作家名 local search 【保留】

- ローカルで openBD 全 ISBN (~10M) を一括 download (~3 時間)
- 既知作家 6,751 名で絞り込んで軽量 JSON (~5-15MB) を commit
- CI 側で SQLite に import、`openbd_author_adult_ratio` signal を追加
- **判断**: ユーザ指示で保留。スケールに対してインフラ投資が重い、NDL の補完としては有用だが現在の adult 検出は十分機能している
- 詳細設計は plan file (`/root/.claude/plans/root-claude-uploads-ec200ecf-2ecf-48eb-snappy-coral.md`) の下半分に保管

### 案 B. Amazon PA-API `SearchItems` (Author 検索) 【将来本命】

- PA-API 5.0 の `SearchItems(Author=...)` で 1 作家 ~100 件 (10page × 10item) を取得
- BrowseNode `成年コミック` 含有を direct チェック → adult 判定の決定打
- ASIN 直接取得 → affiliate link 即生成可能
- カバー画像も Amazon CDN 経由で ToS 準拠
- **gate**: PA-API 承認 (180日以内 3 売上) = Phase 5 アフィリエイトサイト公開後
- **判断**: 本命。openBD よりも筋が良い (アフィリエイト target そのもの、adult 判定が direct、ASIN/画像も同時取得)

## Phase 5 までに進められる準備

完了:

- ✅ **schema 先行 migration** (2026-05-05, schema_version 4 → 5):
  - `amazon_metadata` テーブル新設 (PK = asin)。columns: `isbn13` (volumes への弱 FK), `browse_node_path` ("Books > コミック > 成年コミック" 等), `is_adult_browse_node` (0/1), `sales_rank`, `fetched_at`
  - 既存 `volumes.asin` / `volumes.cover_url` / `asins` table はそのまま (ASIN cache + locale variants で十分)
  - PA-API 承認まで空のまま。 Phase 5 開始時に migration 不要で書き込み可
  - 当初 `editions.amazon_asin` / `editions.amazon_image_url` を提案していたが、 ASIN 階層は volume レベルが正しいため amazon_metadata sidecar table に修正
- ✅ **Volume schema 拡張** (2026-05-07): `kindle_asin` (Kindle 版 ASIN) + `description` (巻ごとの説明文) を VolumeSchema に追加。 PA-API 投入時にそのまま受け入れ可
- ✅ **Manga schema 拡張** (2026-05-07): `anime_adapted` / `anime_first_year` / `alternative_titles` (en/fr/de/it/pt) / `awards` / `wikidata_qid` を MangaSchema に追加。 21 canonical + 10 newer (auto-promote) に手動 populate 済 (= 計 31 件)
- ✅ **Frontend MVP + CI auto-deploy** (2026-05-07): Next.js 15 + Tailwind の静的 export + Cloudflare Workers Assets 配信。 push trigger で 自動 build + deploy (`deploy-cloudflare.yml`)、 Android 端末完結ループ確立

未着手:

1. Associate Tag 取得 / 申請プロセス
2. 成年コミック BrowseNode ID の human 探索 (Amazon.co.jp 公開ページ経由、認証不要)
3. PA-API 5.0 SDK 選定 (公式 SDK 廃止済 → community SDK or SigV4 自前署名)
4. `computeAdultScore` への `amazon_browse_node_adult` signal 追加 (Phase 5 開始時)

## 残タスク (2026-05-07 時点)

### 短期 (家事系)
- 残り 10 件 (= title から内容判別不可な作品) の anime/alt_titles/awards 補完 — 手動 / 自動 fetcher
- 詳細ページの微調整 (= ユーザ判断待ち)

### 中期 (拡張)
- B1: 専用集計ページ — `/publishers/[key]`, `/mangaka/[name]`, `/magazines/[key]`, `/genres/[key]`, `/anime-adapted`, `/awards`
- B2: 検索 box 分離 (作品 / 漫画家 / 出版社) + autocomplete
- B3: wikidata_qid 自動取得 fetcher (series.title から Wikidata 検索 → QID)

### 長期 / Gate 待ち (Phase 5 PA-API 承認後)
- C1: 巻単位 description (Editorial Reviews を grounding に AI rewrite)
- C2: cover_url 投入 (公式 cover image)
- C3: kindle_asin 投入
- C4: adult 検出 BrowseNode 直判定 (倉科遼系の偽陽性根本解決)
- C5: Phase 5 事前準備 (BrowseNode ID 探索 / SDK 選定 / mock fetcher) — gate 待ち中でも可

### 運用
- D1: 6,751 名 全件 run (本番スケール検証)
- D2: fetch:wikipedia Layer A 改善 (検索ロジック改善で hit rate 18% → 30%+) — Phase 5 PA-API でカバーされるなら不要

---

# 2026-05-08 セッション: MADB pipeline 構築 + Tier 1 完了

## 経緯と動機

ユーザが既存 NDL pipeline (= `Wikidata QID → CSV alt_names → NDL CQL → ISBN`) の構造的限界に問題意識を持ち、 別作家混入 (false-positive) を量産する 「作家名キー駆動」 から **「ISBN list を別 source から取得 → openBD で metadata 生成」** に方向転換したいと希望。 候補として MADB (メディア芸術データベース、 文化庁 LOD) と Google Books を検討、 spec 比較の結果 MADB が圧倒的優位 (= ライセンス CC-BY 4.0 / 漫画 30 万件超 / 雑誌情報 / よみがな) と判断。

ユーザ意思 (= AskUserQuestion で確定):
1. **NDL pipeline は仕組みごと残置** (= `scripts/fetch-ndl.ts` 等は touch しない、 fallback として保持)
2. **データは MADB 由来に置換** (= 既存 NDL volume は MADB が INSERT/UPDATE で上書き)
3. **実装スコープは fetch のみ** (= promote / yaml export / workflow 統合は別プラン)

## 完成した成果物

### 新規ファイル
- `scripts/probe-madb.ts` (~570 行): MADB SPARQL endpoint への probe + schema discovery + per-author 結果 dump (read-only)
- `scripts/fetch-madb.ts` (~700 行): 本格 fetcher。 fetch-ndl の VolumeStmts pattern を踏襲、 MADB SPARQL → DB upsert
- `.github/workflows/probe-madb.yml`: probe を GH runner で実行 (= sandbox は SPARQL endpoint へ届かない)
- `.github/workflows/fetch-madb.yml`: fetch:madb 6 QID loop + fetch:wikipedia + db:report + artifact upload
- `docs/madb-probe.md`: probe 結果レポート (= 自動生成、 raw response sample 込み)

### 編集
- `package.json`: `probe:madb` / `fetch:madb` script 追加
- `scripts/db-report.ts`: `--series` で `publisher_key/magazine_key` 列 + 全体 fill rate を表示
- `MEMORY.md`: このセクション

### 不変 (= 明示的に touch しない)
- `scripts/fetch-ndl.ts` 等の既存 fetcher
- `db/schema.sql` (= sources テーブル既存、 拡張不要)
- `lib/edition.ts` (= `normalizeIsbn13` / `buildSeriesKey` 等を import)
- 既存 13 yaml (= 別プランで再生成予定)

## MADB の data model (= 5 ラウンドの SPARQL probe で判明)

### Endpoint と vocabulary
- 正規 SPARQL endpoint: `https://mediaarts-db.artmuseums.go.jp/sparql` (= **`bunka.go.jp` ではない**、 過去の試行で誤認していた)
- schema prefix: **`https://schema.org/`** (= http でなく **https**)
- class prefix: **`https://mediaarts-db.artmuseums.go.jp/data/class#`** (= `/ns/class#` ではない)
- property prefix: `https://mediaarts-db.artmuseums.go.jp/data/property#`
- HTTP: POST + form-urlencoded (= GET は URL 長制限と CDN cache で不安定)

### 主要 class (件数)
| Class | 件数 | 役割 |
|---|---|---|
| `Supplement` | 1,681,828 | 補足情報 (= 巨大だが leaf 多い) |
| `MangaBook` | 397,250 | **漫画単行本 manifestation** ← 我々の対象 |
| `AnimationTVProgram` | 197,665 | (アニメ) |
| `MangaMagazineIssue` | 179,908 | 雑誌の各号 |
| `MangaBookSeries` | 139,130 | 単行本シリーズ |
| `Agent` | 74,791 | 作家 / 出版社 |
| `MangaMagazinePublication` | 30,023 | 雑誌掲載 (= 連載作品) |
| `MangaMagazine` | 5,753 | 雑誌全体 |

### MangaBook の outgoing predicates (= fetch:madb で使う構造)
- `schema:creator` → **literal** (= Agent URI でなく `"[著]諫山創"` 等の文字列)。 役割タグ prefix 込み
- `schema:isbn` → ISBN 文字列
- `schema:publisher` → literal `"講談社　∥　コウダンシャ"` (= 漢字 ∥ カナ、 全角空白)
- `schema:datePublished` → `2020-05` 形式
- `schema:isPartOf` → **MangaBookSeries の C-id URI** (= 雑誌ではない、 確認済)
- `rdfs:label` → タイトル

### 重要発見: creator literal は役割タグ prefix
| 表記例 | 件数 (諫山創 例) |
|---|---|
| `[著]諫山創` | 48 |
| `[原作]諫山創` | 40 (= スピンオフ "進撃!巨人中学校" 等) |
| `諫山創` (bare) | 1 |

→ 完全一致 filter では bare 表記しか拾えない。 **REGEX `(^|\]|,|[ 　])NAME($|,|[ 　\]])` で末尾固定** + 役割タグ + 共著連結 (`[著]A,B`) を吸収。 `STR(?creator)` で literal 文字列を比較。

## Tier 1 実装結果 (= ユーザ「Tier 1 やって」 指示)

### Task 1: 関連書籍 / extra-vol → edition.type=other 分離
**問題**: 「金色のガッシュ!! 通常版 vols=67、 no=1..33」 (= 1巻あたり ~2 record) のような重複表示。 真因は `extractVolumeNumber` が null を返すケース (= "全巻パック" "ガイド本" "セット商品") を vol_number=1 で fallback していたこと。

**修正**: `volumeNumber === null && type === "standard"` を `type='other'` に分離。 fetch-madb.ts の `upsertVolume` 内。

**結果**: あさドラ! (8件全て other) / 金色のガッシュ!! (16件 other に分離) / Masterキートン / 進撃!巨人中学校 / 素晴らしい世界 で改善。

### Task 2: publisher literal split + master 解決
**問題**: MADB は publisher を `"講談社　∥　コウダンシャ"` (= 漢字 ∥ カナ) で発行。 `editions.imprint` にそのまま保存すると downstream で表示が汚い。

**修正**:
- `splitMadbLiteral(s)` helper で `∥` の前 (= 漢字部分) のみ抽出
- `publishers.yml` master と name 完全一致で `publisher_key` 解決
- `series.publisher_key` に `COALESCE` で UPDATE

**結果**: **publisher_key fill rate = 118/123 (96%)**。 集英社 / 小学館 / 講談社 / 白泉社 等は完全一致。 5件未解決は `クラーケンコミックス` (= 金色のガッシュ完全版 出版社) 等の master 不在 publishers。

### Task 3: magazine_key 解決 (= 5 ラウンド試行錯誤の末、 fetch:wikipedia に委譲)

**結論**: **MADB は単行本 → 雑誌 の link を構造的に保持していない**。 ユーザの UI screenshot (= 進撃の巨人 33 詳細ページ) で「関連リソース ① — 諫山創 (責任主体)」 のみが表示されることからも確認。 単行本の関連リソースは**作家のみ**で、 雑誌は無い。

**5 ラウンドの SPARQL probe 結果**:
1. ✗ `schema:isPartOf` の値は MangaBookSeries の C-id URI で、 MangaMagazine ではない
2. ✗ `schema:isPartOf+` (property path) で多 hop しても MangaMagazine に届かない
3. ✗ MangaBookSeries の outgoing entity link は **Agent (= creator) のみ**、 MangaMagazine 直接 link 0 件
4. ✗ MangaMagazinePublication は leaf entity (= 他 entity への link 無し)
5. ✗ (name, creator) で BookSeries ↔ MagazinePublication を bridge する案も exact match 失敗 (= 進撃の巨人 で確認)

→ 173k 件の `incoming schema:isPartOf to MangaMagazine` はすべて **MangaMagazineIssue から**。 単行本サブグラフから雑誌サブグラフへの渡る predicate が**存在しない**。

**最終決定** (= ユーザ承認、 推奨案):
- MADB から magazine 取得は諦める (= graph 構造的に不可能と判断)
- 既存の `fetch:wikipedia` で magazine_key を補完 (= NDL pipeline で実証済)
- データ責務分担:
  | source | 担当 |
  |---|---|
  | **MADB** | ISBN / publisher_key / volume_number / release_date / edition.type |
  | **Wikipedia** | magazine_key / title_kana / genres / synopsis / demographic |

**コード変更**: `scripts/fetch-madb.ts` から magazine 関連 code を全削除 (= `magazines.yml` 読込、 `updateSeriesMagazineKey`、 `magazineKey` resolve 経路、 `discoverIsPartOfChain` Phase 0+ など)。 `.github/workflows/fetch-madb.yml` に `fetch:wikipedia` step 追加 + 探索用 debug step を全削除。 -255 / +32 lines で大幅 simple 化。

## Workflow 構成 (= 一気通貫)

```
db:init
  → import:masters (= publishers.yml + magazines.yml)
  → import:mangaka (= 6,751 mangaka CSV)
  → fetch:madb (= 6 QID loop)            ← MADB 担当
  → fetch:wikipedia                      ← Wikipedia 担当
  → db:report (= 結果検証)
  → artifact (= db.sqlite + raw dumps)
```

## 6 作家 probe / fetch の最新結果 (= 7-8 回目 GH run)

| 作家 | QID (= CSV 真値) | hits | unique ISBN | 主要 series |
|---|---|---|---|---|
| 諫山創 | Q3782468 | 89 | 89 | 進撃の巨人 (54件) + 派生 6 series |
| 高屋奈月 | Q241885 | 79 | 76 | フルーツバスケット (35件) + Another (4) + 他 |
| 浦沢直樹 | Q348436 | **328** | 265 | YAWARA! (65) / Masterキートン (25) / 20世紀少年 (23) / Pluto (15) / Billy Bat (20) 等 |
| 浅野いにお | Q600217 | 63 | 63 | おやすみプンプン (22) / DDD (19) / 他 |
| 吾峠呼世晴 | Q24865213 | 33 | 33 | 鬼滅の刃 (25) + キメツ学園! (6) |
| 雷句誠 | Q972529 | 131 | 121 | 金色のガッシュ!! (83件、 通常+完全+その他) / どうぶつの国 (14) / 等 |

**DB 投入結果**:
- series: 123
- editions: 131 (= Task 1 の other 分離で +7)
- volumes: 689
- sources `madb`: 689 行
- publisher_key fill: **118/123 (96%)**
- magazine_key fill: 0/123 (= fetch:wikipedia 後段で埋まる想定、 未確認)

## 重要な hardcode 修正 履歴

私 (Claude) が初期に hardcode した QID が CSV と全部不一致で、 fetch-madb で mangaka resolve 失敗 → 0 件投入した bug があった。 修正済 commit `7cb1815`:

| 作家 | 旧 (誤、 私の Wikidata 知識違い) | 新 (CSV 真値) |
|---|---|---|
| 諫山創 | Q11331084 | **Q3782468** |
| 高屋奈月 | Q231007 | **Q241885** |
| 浦沢直樹 | Q310385 | **Q348436** |
| 浅野いにお | Q1145902 | **Q600217** |
| 吾峠呼世晴 | Q56022442 | **Q24865213** |
| 雷句誠 | Q1366247 | **Q972529** |

probe-madb は QID 使わず name literal で SPARQL を叩いていたので結果自体は正しかったが、 表示 QID は誤値だった。

## SQLite NOT NULL 違反 修正 履歴

`fetch-madb` 初版で series=N / editions=0 / volumes=0 になった bug。 原因: スキーマの NOT NULL 制約見落とし。 修正済 commit `ae3e1d8`:

- `editions.label NOT NULL` → `EDITION_LABELS[type]` (= "通常版" / "完全版" 等) を渡す
- `volumes.number NOT NULL` → `volumeNumber ?? 1` + null 時は `is_extra=1` flag

`upsertVolume` は try/catch で各 record 独立処理するため、 series insert 成功直後の edition insert で SQLite NOT NULL 違反 → catch で skip → 次 record、 という流れで series だけ commit されていた。

## 未解決の課題 (= Tier 2 候補)

### 1. 重版 ISBN の集約 (= 同 vol_number で複数 ISBN)
**症状**: 進撃の巨人 standard vols=54 だが no=1..34 (= 34 巻なのに 54 record、 vol1×2 / vol8×2 等)。 鬼滅の刃 vols=25 (= vol20×2, vol21×2)。 フルーツバスケット vol1..vol8 各 ×2。

**原因**: MADB は同一巻の複数 ISBN (= 通常版 + 限定版 + コンビニコミック + 重版) を独立 manifestation として保持している。 fetcher は data fidelity を保つため raw に投入。

**対処**:
- A. fetch 段で `(series, type, vol_number)` 単位で 1 ISBN に正規化 (= 最古発行を採用、 他は別 edition.type='other' か skip)
- B. promote 段で正規化 (= yaml 出力時に重複排除)
- C. 重版を edition.type='renewal' / 'other' に細分化

ユーザと方針相談すべき。

### 2. fetch:wikipedia の実走確認
fetch-madb workflow に追加した `fetch:wikipedia` step がまだ実行確認できていない。 期待: magazine_key fill rate が数十/123 になる。 次 run で要確認。

### 3. promote:bulk の MADB 対応
現状 promote:bulk は NDL fetch を前提にしている可能性。 MADB データから yaml 生成できるよう調整が必要。 別プラン。

### 4. 既存 13 yaml の MADB 再生成
現状の `data/manga/*.yml` (= 13 件、 NDL 由来) を一旦削除 → MADB run で再生成。 ユーザの「データ置換」 意思の最終形。

### 5. bulk-promote-test workflow への統合
現状 fetch-madb は standalone workflow。 bulk-promote-test に組み込む案は「Out of scope」 と plan に明記、 別プラン。

### 6. publisher master 不在 publishers の補完
118/123 = 5件未解決。 例: クラーケンコミックス (= 金色のガッシュ完全版)。 `data/publishers.yml` master を拡張するか、 fuzzy match を追加するか。

### 7. MADB 未収録作家の fallback
ユーザ意思 1 (= NDL 仕組みは残置) は、 MADB hit=0 のとき NDL fetch を起動する fallback ロジックを将来書く可能性を残している。

## 関連 commit (= 開発履歴の trail)

```
8dccac4  feat(fetch-madb): Phase 0+ schema discovery for schema:isPartOf chain
fcadf68  ci(fetch-madb): direct SPARQL probe for MangaBookSeries → MangaMagazine link
ff33762  ci(fetch-madb): pivot via MangaMagazinePublication for magazine link
a0dc91f  ci(fetch-madb): probe MangaMagazinePublication chain via incoming predicates
3eeee91  feat(fetch-madb): close Tier 1 — magazine_key delegated to fetch:wikipedia
d769cb6  feat(db-report): show publisher_key/magazine_key in --series view
c5889c1  feat(fetch-madb): Tier 1 — extra-vol split, publisher/magazine resolve
ae3e1d8  fix(fetch-madb): satisfy NOT NULL constraints for editions.label / volumes.number
7cb1815  fix(madb): correct hardcoded QIDs to match data/seed/mangaka.csv
18642a9  feat(fetch-madb): MADB SPARQL fetcher (NDL pipeline と並走)
9980ee6  fix(probe-madb): treat schema:creator as literal (not URI ref)
033d5bb  fix(probe-madb): match creator with role-tag prefix via REGEX
2e5296f  fix(probe-madb): apply real vocabulary discovered via Phase 0+
6efda01  feat(probe-madb): add Phase 0+ schema discovery to find real vocabulary
df2a759  fix(probe-madb): use correct endpoint artmuseums.go.jp + MangaBook vocabulary
fa002bf  ci(probe-madb): add workflow_dispatch to run MADB probe on GH runner
a475e1e  probe(madb): narrow scope to MADB only, drop Google Books
c879e72  probe(isbn-sources): add Google Books + MADB comparison probe
```

## プロセス上の反省 (= 今後のセッションで注意)

ユーザに **「相談してほしかった」** と指摘された。 magazine_key の探索で 5 ラウンドの GH workflow run を消費した直後、 ユーザが UI screenshot (= 進撃の巨人 33 の関連リソース欄) を提示し、 「関連リソース 1件 = 作家のみ」 = 単行本に雑誌 link なしが UI 上から自明だった。

**次セッションの行動指針**:
1. **API を叩く前に UI / 公式ドキュメントで data モデルを先に確認** する。 文化庁 LOD はドキュメント整備されているはず
2. **仮説が 2 回連続外れたら iterate でなく相談に切り替える**。 「これは MADB の構造的制限と思われます。 UI で確認できますか?」 のような短い質問で済む話だった
3. **GH workflow run を消費する前に**、 ユーザに UI / docs 確認を依頼する選択肢を提示する
4. ユーザは Android スマホで UI を確認可能。 こちらが見えない情報 (= UI / 内部 data 構造) は積極的に依頼してよい

## 次セッションでの推奨スタートアクション

1. このファイル (`MEMORY.md`) を Read
2. `git status` と `git log -10 --oneline` で進捗を把握
3. ユーザに「Tier 2 (= 重版 ISBN 集約 / promote 統合 / yaml 再生成 / bulk-promote-test 統合) のどれから進めますか?」 と聞く
4. もしくは fetch:wikipedia 実走確認の結果次第では magazine_key fill rate の確認 + 不足分の対処
5. ユーザの方針が定まらないなら、 「未解決の課題」 セクションから tractable な 1 件を提案

## ブランチ

- 開発ブランチ: `claude/manga-database-affiliate-3x0ms`
- すべての変更はこのブランチ上で commit/push
- main へ merge していない (= ユーザの判断待ち)
