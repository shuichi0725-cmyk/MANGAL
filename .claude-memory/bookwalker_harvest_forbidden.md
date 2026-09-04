---
name: bookwalker_harvest_forbidden
description: 【禁止】BOOK☆WALKER(bookwalker.jp)は試し読み収集不可=robots.txtがClaudeBotを全面Disallow+試し読みURL(/de*/?sample=*)を全crawlerにDisallow
metadata:
  type: project
---

ユーザ質問「bookwalker.jp は試し読みを BookLive! と同じ様に収集は無理かな？」(2026-09-04)への調査結果。
**答え = 収集しない**。robots.txt(2026-09-04 実取得)で二重に禁止されている:

1. `User-agent: ClaudeBot` / `Disallow: /` = **サイト全体がClaudeBot拒否**。GPTBot/CCBot/Google-Extended/
   Applebot-Extended/Meta-ExternalAgent/Bytespider も同様に全面Disallow。
2. `User-agent: *` の側に `Disallow: /de*/?sample=*` = **試し読みURLそのものが全crawler禁止**
   (BOOK☆WALKERの商品頁 `/de<UUID>/` の `?sample=` が試し読み)。

= 「取れるか」以前に**取ってはいけない**。robots.txt 以外の頁は一切fetchせずに調査を止めた。

## 仕組みの面でも BookLive 方式は移植できない
BookLiveが安く回せたのは cid が **`<title_id>_<巻3桁>` と決定的**で、シリーズ1件の検索さえ通れば
あとはHEADで全巻展開できたから([[tameshiyomi_harvest]])。BOOK☆WALKERの商品URLは
**巻ごとに独立したUUID**(`/de<uuid>/`)で、シリーズID+巻番号から導出できない。
= 全巻を知るにはシリーズ一覧頁をcrawlするしかない = 規約違反の度合いが上がるだけ。

## 正規ルート(やるならこれ)
アフィリエイト提携経由の**公式商品データ/API**。スクレイピングでなく提携先が配る形式なら合法。
[[ebook_store_sheet_homework]](電子書籍ストア一覧シート=アフィ申請通過後に着手)と同じ扱いにする。

## How to apply
- 新しい試し読み/書誌の情報源を検討する時は、**まず robots.txt を取る**。ClaudeBot が Disallow なら
  そこで終わり(=他の頁を試し打ちして確かめない)。[[booklive_access_incident]] の再発防止と同じ姿勢。
- 「大手だから平気」「HEADだけなら平気」は根拠にならない(BookLive事故の直接原因)。
