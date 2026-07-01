---
name: rakuten-cover-data-asset
description: 楽天収穫(.cache/rakuten-isbn.jsonl)=ISBN単位で書影/アフィリンク/価格/発売日。noimage除外必須。cover_url流し込み手法
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

楽天ブックスAPI収穫の生データ = **`.cache/rakuten-isbn.jsonl`**(2026-06-14完走、約18万レコード=181,595行・276MB。gitignore=中間データ)。
1行 = `{"isbn": "...", "item": {...}}`。item の有用フィールド:

- **書影**: `largeImageUrl`(200x200) / `mediumImageUrl`(120) / `smallImageUrl`(64)。`?_ex=WxH` で表示サイズ指定。
- **収益**: `affiliateUrl`(楽天アフィリンク・タグ済) / `itemUrl`。`itemPrice` / `listPrice` / `discountRate` / `discountPrice`。
- 他: `salesDate`(発売日・和文) / `publisherName` / `author` / `itemCaption`(あらすじ) / `seriesName`。

★**罠 = noimage プレースホルダ**: 書影が無い本は largeImageUrl が `.../noimage_01.gif` を返す。表紙として拾わない(URLに "noimage" 含むら除外)。AKIRA等は1巻ISBNが楽天に実書影なし。

**書影流し込み(実装済 `scripts/_fill-preview-covers.py`)**: ISBN13一致で各 `editions[].volumes[].cover_url` に純粋追加。ISBN10混在は `to_isbn13` 正規化必須。
- フロントは対応済み: `coverUrl(manga)` ([[clustering_unit_is_series]]でなく lib/schema.ts)=1巻優先・無ければ表紙ある巻フォールバック。MangaCard / 詳細ページが使用。`next.config` の images.remotePatterns に `thumbnail.image.rakuten.co.jp` 追加済。CoverImage は src=null/onErrorで非表示。
- 2026-06-14 テスト環境(mangal-preview)で **564/600作に表示**を実証。[[store_affiliate_architecture]] [[openbd_eol_amazon_required]]

★**永続バックアップ(2026-06-16, ユーザ指示「消えないように」)**: `.cache` は gitignore で消えるため、高コスト収穫を **`data/seeds/harvest/` に git追跡**で永続化。`rakuten-isbn.jsonl.gz`(61MB無損失) + `ndl-cache.tar.gz`(NDL SRU生応答34MB等20ファイル)。復元= `gzip -dc .../rakuten-isbn.jsonl.gz > .cache/rakuten-isbn.jsonl` / `tar -xzf .../ndl-cache.tar.gz -C .cache`。再収穫で増えたら作り直してcommit。手順は harvest/README.md。

★**本番への焼込ルート(2026-06-16 実施)= db-v2 経由**: `_fill-preview-covers.py` は preview出力yml に流す方式だが、**本番 manga.v2 は promote が `db-v2.volumes.cover_url` から書影を読む**(楽天jsonlを promote時に join しない)。なので本番反映は **promote前に rakuten-isbn.jsonl → db-v2 の volumes.cover_url に取込**(isbn13一致・noimage除外・null のみ純粋追加)→ promote で焼込。2026-06-16実施で **201,632巻取込(全382,704中52%)**、本編コナンは全107巻に書影。★db-v2は.cache(再生成で消える)ので、db-v2フル再構築後は cover再取込が必要(jsonlから何度でも再生成可)。
