# harvest = 高コスト収穫データの永続バックアップ(楽天種 / NDL種)

`.cache/` は gitignore で消える領域。ここに在る収穫は **1req/秒のレート制限で数日かかる**ため、
消失すると再取得が極めて高コスト。よって gzip / tar.gz で git 追跡し永続化する(ユーザ指示 2026-06-16)。

## 中身
- `rakuten-isbn.jsonl.gz` = 楽天ブックスAPI収穫(ISBN単位の書影/アフィリンク/価格/発売日/itemCaption)。
  246,228 行。展開先 = `.cache/rakuten-isbn.jsonl`(357MB)。[[rakuten-cover-data-asset]]
- `ndl-cache.tar.gz` = NDL SRU 収穫一式(20ファイル)。中核 = `ndl-sru-raw-cache.json`(34MB 生SRU応答) +
  `ndl-by-isbn.json`(ISBN→書誌)。展開先 = `.cache/`。

## 復元(.cache が消えた時)
```bash
gzip -dc data/seeds/harvest/rakuten-isbn.jsonl.gz > .cache/rakuten-isbn.jsonl
tar -xzf data/seeds/harvest/ndl-cache.tar.gz -C .cache
```

## 更新(再収穫で増えたら)
収穫スクリプトは `.cache/` に追記する。区切りの良い所で上記を作り直して commit(=スナップショット更新)。
```bash
gzip -c -6 .cache/rakuten-isbn.jsonl > data/seeds/harvest/rakuten-isbn.jsonl.gz
tar -czf data/seeds/harvest/ndl-cache.tar.gz -C .cache $(cd .cache && ls *ndl*.json *ndl*.tsv 2>/dev/null | sort -u)
```

## 著作権メモ(使用時)
- 事実フィールド(ISBN/題/著者/出版社/価格/発売日)= 著作権対象外、自由。
- `itemCaption`(あらすじ/商品説明)= 出版社の著作物 → **逐語表示はNG、AI要約して中立化**してから使う。
- 書影 = 著作物。楽天配信URL(thumbnail.image.rakuten.co.jp)の **hotlink 表示のみ可**(DL再ホストNG)。
