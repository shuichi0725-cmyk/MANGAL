---
name: rakuten-harvest-page-cap
description: 楽天BooksBook/Searchは1クエリ最大100頁=3,000件。予約harvestは発売日降順なので上限で切れると当月〜近未来の新刊が毎回黙って落ちる。2026-09-24に警告+上限100化(その他71/100頁)。chirayomiUrl/limitedFlagは手元81.8万件で値0
metadata:
  type: reference
---

公式ドキュメント(https://webservice.rakuten.co.jp/documentation/books-book-search・2017-04-04版)で確認した事実:
- **page 1〜100・hits 最大30 = 1クエリ最大3,000件**。pageCount も100で頭打ち。
- `size` の値: 0全て/1単行本/2文庫/3新書/4全集・双書/5事典・辞典/6図鑑/7絵本/8カセット,CD等/9コミック/10ムックその他。
- `sort`: standard / sales / ±releaseDate / ±itemPrice / reviewCount / reviewAverage。
- ドキュメントに載るが**実際には値が来ない**: `chirayomiUrl`・`limitedFlag`(手元の楽天キャッシュ81.8万件で非空0件)
  = 試し読み源・特装版判定には使えない。`contents`(全集/セットの収録)は2%に入る。
- Referer/Origin はドキュメントに無いが、無いと400(実測・_lookup.py 等は付けている)。

**予約harvest(`_rakuten-preorder-harvest.py`)への帰結**: 6サブジャンルを発売日降順でたどるので、頁上限で切れると
**列の後ろ=当月〜近い未来**が落ち、毎回同じ所で切れる=恒久的な取りこぼし。2026-09-24 実測で「その他」71頁
(旧上限80頁の89%)。→ 既定100頁+各ジャンルが過去日付まで届いたかの判定+★★警告(commit 本日)。
100頁でも足りなくなったら**ジャンル細分**(下位ジャンル/出版社)で取る。状態= `.cache/preorders/harvest-status.json`。
関連: [[rakuten_out_of_stock_flag]] [[daily_distill_hold_not_requeued]]
