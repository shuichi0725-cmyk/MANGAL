# MANGAL Project Memory

> このファイルは Claude Code session の context bootstrap 用。新しいセッションを開始したら最初に読むこと。

最終更新: 2026-05-05

## プロジェクト概要

- 漫画作品の Japanese database (NDL Search ベース)
- 最終ターゲット: Amazon アフィリエイトサイト
- 戦略原則: **Amazon カバー画像 / 価格 / 在庫のみ使用**。NDL/openBD/Rakuten 等の画像・価格は不使用 (Phase 5 で PA-API 承認後に Amazon に切替)
- 現在 Phase 4 相当 (DB 整備 + bulk-promote pipeline)、Phase 5 = Amazon PA-API 承認待ち

## 主要ファイル

- `db/schema.sql`: 現行 schema_version = 4 (Fix C で 3 → 4)
- `scripts/promote-bulk.ts`: NDL → series/editions 自動 promote。adult 検出ロジック (`computeAdultScore`) 含む
- `scripts/fetch-adult-lists.ts`: JA Wikipedia から adult publishers / mangaka リスト取得 (Fix C)
- `scripts/fetch-ndl.ts`, `scripts/fetch-wikidata.ts`: 既存の主要 fetcher
- `lib/edition.ts`: `normalizeCreatorName`, `matchAdultPublisher` 等の utility
- `data/seeds/adult-publishers-manual.yml`: 白夜書房等の manual seed (Wikipedia 抽出に出ない補完)
- `.github/workflows/bulk-promote-test.yml`: CI 試験 workflow (試金石作家 run)

## 現在の adult 検出設計 (Fix C, 2026-05 完成)

`computeAdultScore` は 3 signal (additive、threshold = 3) で判定:

| Signal | Source | Weight |
|---|---|---|
| `wikidata_hentai_credit` | mangaka.has_adult_credit (Wikidata P136=Q172241) | +3 |
| `wikipedia_adult_mangaka_list` | adult_mangaka_known テーブル (Wikipedia「日本の成人向け漫画家の一覧」) | +2 |
| `adult_publisher_imprint` | adult_publishers テーブルとの imprint マッチ (Wikipedia「成人向け漫画雑誌の一覧」+ manual seed) | +3 |

**`adult_score >= 3` で promote-bulk が draft skip**。試金石 run #11 (qids=Q193300 Q1121064) で:

- 唯登詩樹 ジャンクション/Uma・uma (白夜書房) → score=5 → skip ✅
- 唯登詩樹 集英社/講談社 一般作品 (Kirara, Yui shop, ボクのふたつの翼 等) → score=2 → drafted ✅
- 手塚治虫 全 13 シリーズ → score=0 → drafted ✅

`adult_publishers` は精選 21 件 (五十音/ノイズ/「○○書店」等を除外)。

## 試金石 (canary) 作家

- **Q193300 = 手塚治虫**: 一般中心。false positive 検出用
- **Q1121064 = 唯登詩樹**: adult/general 混在型。mixed-portfolio 検出用 (難ケース)

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

## Phase 5 までに進められる準備 (今は未着手)

1. Associate Tag 取得 / 申請プロセス
2. 成年コミック BrowseNode ID の human 探索 (Amazon.co.jp 公開ページ経由、認証不要)
3. `editions.amazon_asin` / `editions.amazon_image_url` 列の予約 (schema migration)
4. PA-API 5.0 SDK 選定 (公式 SDK 廃止済 → community SDK or SigV4 自前署名)

## 次セッションでの推奨スタートアクション

1. このファイル (`MEMORY.md`) を Read
2. `git status` と `git log -5 --oneline` で進捗を把握
3. 直近の bulk-promote-test workflow run を確認 (mcp__github tools 経由)
4. ユーザの指示を待つ。指示が無ければ「未解決の課題」セクションから tractable な next task を提案

## ブランチ

- 開発ブランチ: `claude/manga-database-affiliate-3x0ms`
- すべての変更はこのブランチ上で commit/push
