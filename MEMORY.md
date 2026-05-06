# MANGAL Project Memory

> このファイルは Claude Code session の context bootstrap 用。新しいセッションを開始したら最初に読むこと。

最終更新: 2026-05-06

## プロジェクト概要

- 漫画作品の Japanese database (NDL Search ベース)
- 最終ターゲット: Amazon アフィリエイトサイト
- 戦略原則: **Amazon カバー画像 / 価格 / 在庫のみ使用**。NDL/openBD/Rakuten 等の画像・価格は不使用 (Phase 5 で PA-API 承認後に Amazon に切替)
- 現在 Phase 4 相当 (DB 整備 + bulk-promote pipeline)、Phase 5 = Amazon PA-API 承認待ち

## 主要ファイル

- `db/schema.sql`: 現行 schema_version = 6 (5 → 6: adult_imprints 追加 [Tier 2])
- `scripts/promote-bulk.ts`: NDL → series/editions 自動 promote。adult 検出は `lib/adult-score.ts` 経由
- `lib/adult-score.ts`: `computeAdultScore` の純関数実装 + 27 件の unit test (`lib/adult-score.test.ts`)
- `lib/adult-imprints.ts`: `data/seeds/adult-imprints.yml` の Zod schema + reader
- `scripts/fetch-adult-lists.ts`: JA Wikipedia から adult publishers / mangaka リスト取得 (Fix C)
- `scripts/seed-adult-imprints.ts`: yaml seed → adult_imprints テーブル INSERT (Tier 2)
- `scripts/clean-imprint-dump.ts`: raw imprint dump → adult-imprints.yml 生成 (Tier 2)
- `scripts/fetch-ndl.ts`, `scripts/fetch-wikidata.ts`: 既存の主要 fetcher
- `lib/edition.ts`: `normalizeCreatorName`, `matchAdultPublisher` 等の utility
- `data/seeds/_raw-imprint-dump.txt`: ユーザ提示の raw imprint→publisher dump (~339 entry)
- `data/seeds/adult-imprints.yml`: 整形済 adult imprint seed (252 imprints + 14 distribution_channels + 13 ambiguous)
- `data/seeds/adult-publishers-manual.yml`: 白夜書房等の manual seed (Wikipedia 抽出に出ない補完)
- `.github/workflows/bulk-promote-test.yml`: CI 試験 workflow (試金石作家 run)

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

未着手:

1. Associate Tag 取得 / 申請プロセス
2. 成年コミック BrowseNode ID の human 探索 (Amazon.co.jp 公開ページ経由、認証不要)
3. PA-API 5.0 SDK 選定 (公式 SDK 廃止済 → community SDK or SigV4 自前署名)
4. `computeAdultScore` への `amazon_browse_node_adult` signal 追加 (Phase 5 開始時)

## 次セッションでの推奨スタートアクション

1. このファイル (`MEMORY.md`) を Read
2. `git status` と `git log -5 --oneline` で進捗を把握
3. 直近の bulk-promote-test workflow run を確認 (mcp__github tools 経由)
4. ユーザの指示を待つ。指示が無ければ「未解決の課題」セクションから tractable な next task を提案

## ブランチ

- 開発ブランチ: `claude/manga-database-affiliate-3x0ms`
- すべての変更はこのブランチ上で commit/push
