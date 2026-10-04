---
name: ebook_only_volumes_mechanism
description: 【機構】電子書籍のみで出た巻を巻の並びの続きに「電子のみ」札で出す(案2・2026-10-04)。seed=ebook-only-volumes.yml、isbn13は持たない
metadata:
  type: project
---

2026-10-04 ユーザ裁定「案2」(無人島でエルフと共同生活@COMIC: 紙1〜8巻・9/10巻は電子のみで完結)。
選択肢は 1注記だけ / 2巻の並びの続きに札付き / 3電子版タブ / 4帯 で、**2** を採用。

- seed `data/seeds/ebook-only-volumes.yml`(キー=SRC slug)→ promote が**全edition操作の後・書影最終充填の前**に
  edition_type の先頭の版(刷タブにも)の末尾へ `ebook_only: true` の巻を足す。同番号が在れば足さない(紙が出たら自然に退く)。
- 巻の欄: `ebook_only`/`kobo_url`(lib/schema.ts)。`kindle_asin` は既存欄。isbn13 は**持たない**
  (電子に振られた番号=10巻 9784867947265 は楽天紙/NDLに無い。ISBN照合・消失監視を壊す)。
- 表示(components/VolumeCoverflow.tsx): サムネに青「電子」札 / 詳細に「📱 電子書籍のみ」+注記(Kobo書影の注意書きは出さない)/
  紙の店(楽天/Yahoo!/Amazon)を隠す / Kindle=/dp/ASIN・Kobo=商品ページへ直接。
- 完結は status-corrections(source=publisher-official)。索引は total_volumes=10・完結。
- ★1件目のみ手で seed 化。 他作品への展開(電子続巻の候補表 kobo-digital-continuation.tsv は7/30から空)は未着手=ユーザ裁定待ち。
関連 [[ebook_only_editions_out_of_scope]] [[version_tabs_stock_ebook]]
