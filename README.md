# MANGAL — 日本の漫画データベース

日本の漫画を出版年・著者・原作者・出版社・分野・ジャンルで絞り込めるカタログサイト。
各作品の購入リンクは Amazon アソシエイト経由で表示する。

## 構成

- Next.js 15 (App Router) + TypeScript + Tailwind CSS v4
- データは `data/**/*.yml` に Git 管理（PR で追加）
- `lib/loadData.ts` がビルド時に YAML をロードし Zod で検証
- ホスティング: Vercel（無料枠）

## セットアップ

```bash
npm install
cp .env.example .env.local   # アソシエイトタグを取得したらここに記入
npm run dev
```

開いたら http://localhost:3000 でトップページ。

## 主なコマンド

| コマンド | 用途 |
|---|---|
| `npm run dev` | 開発サーバ |
| `npm run build` / `npm run start` | 本番ビルド・起動 |
| `npm run typecheck` | TS 型チェック |
| `npm run test` | Vitest（フィルタ純関数） |
| `npm run fetch:openbd -- 9784088725093 ...` | openBD から書誌取得し YAML 雛形生成 |
| `npm run fetch:volumes -- --slug X --isbns A,B,...` | 既存 YAML の `volumes[]` を openBD で一括補完（表紙・発売日） |
| `npm run fetch:mangaka` | Wikidata SPARQL から日本の漫画家一覧を `data/seed/mangaka.csv` に書き出し（成年向けクレジット作家のフラグ付き） |

## データ追加

1. `data/manga/<slug>.yml` を作成（既存ファイルがフォーマットの雛形）。
2. `slug` は小文字英数字とハイフンのみ。`title_kana` と `title_romaji` を埋める。
3. `publisher` / `magazine` / `genres` / `demographic` のキーは
   `data/publishers.yml` / `data/magazines.yml` / `data/genres.yml` / `data/demographics.yml` のキーと一致させる。未定義キーはビルド時にエラー。
4. `volumes[]` に各巻の `number` / `isbn13` / `release_date` 等を入れる（最低1巻分）。`isbn13` を入れると openBD の表紙が自動表示される。
5. 全巻データを揃える時は `npm run fetch:volumes -- --slug <slug> --isbns A,B,C,...` で openBD から `cover_url` と `release_date` を一括補完できる。

ISBN がまとめてあるなら:

```bash
npm run fetch:openbd -- 9784088725093 9784091210562
```

で雛形を作ってから手動で `genres` 等を整える。

## Amazon アフィリエイトの段階導入

### フェーズA（PA-API 承認前）
- `https://affiliate.amazon.co.jp/` でアソシエイト登録（180日以内に3件の適格購入が必要）。
- `.env.local` に `NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG=mangal-22` などを設定。
- 表紙画像は openBD（再配布可）からのみ取得する。Amazon の画像 URL を直貼りしないこと。
- 購入ボタンのリンクは `/dp/{ASIN}?tag=...` または ISBN 検索に `tag=` を付与する形になる（`lib/amazon.ts`）。

### フェーズB（PA-API 承認後）
- `scripts/fetch-paapi.ts`（未実装）を追加して `Images.Primary.Large.URL` を取得し
  `public/covers/<slug>.jpg` に保存、`volume_1.cover_url` を埋める。
- レートリミット（初期 1 req/sec）に注意してバッチ処理する。

## ロードマップ

- [x] Phase 0–4: 雛形・スキーマ・フィルタ UI・openBD スクリプト
- [ ] Phase 5: PA-API 連携（Amazon 公式画像）
- [ ] Phase 6: react-three-fiber を使った「銀河ビュー」（年代を奥行き、ジャンルを色相に）
- [ ] Phase 7: Turso (SQLite) 移行 + 管理 API

### 詳細ロードマップ

データベース自動構築の見積もりと多言語化（英語・仏語・独語…）の方針は [docs/roadmap.md](./docs/roadmap.md) を参照。
- [ ] ユーザ機能（お気に入り・読了マーク）
