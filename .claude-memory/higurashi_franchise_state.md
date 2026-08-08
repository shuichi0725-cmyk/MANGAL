---
name: higurashi_franchise_state
description: ひぐらしは編ごとに別作画者=別頁。4作を新規登録し令の3編混在を分離、掲載誌20頁を是正。残=宙出版アンソロジー頁と雀/デイブレイク系
metadata:
  type: project
---

2026-08-08 にユーザ提供のNDLサーチTSV(331行)+ja.wikipedia「ひぐらしのなく頃に」漫画一覧で全体を確定。
★**編ごとに作画者・掲載誌が違う別作品**なので MANGAL でも編別に頁を建てる(既存もその構成)。

### 新規登録した4作(本番に1巻も無かった)
| 頁 | 作画 | 掲載誌 | 巻 |
|---|---|---|---|
| `…-kai-tsumihoroboshihen` 解 罪滅し編 | 鈴羅木かりん | ガンガンパワード | 4 |
| `…-kokoroiyashihen` 心癒し編 | 影崎由那 | 月刊コンプエース | 1 |
| `…-rei-hoshiwatashihen` 令 星渡し編 | 刻夜セイゴ | 月刊ビッグガンガン | 2 |
| `…-rei-irotoutoshihen` 令 色尊し編 | 夏海ケイ | ガンガンONLINE | 4 |

### ★「令」頁に3編が潰れていた
旧 `higurashi-no-naku-koro-ni-rei` は v1-2=**鬼熾し編**、v3-4=**色尊し編の3-4巻**という接ぎ木で、
色尊し編1-2と星渡し編1-2はどこにも無かった。canonical で鬼熾し編2巻に絞り、残り2編を別頁化。
- `…-rei-ryukishi-2011` は題に編名が欠けていた → 「ひぐらしのなく頃に礼 賽殺し編」に。**令(rei)と礼(rei)が同音**で紛らわしいので注意。
- 鬼隠し編の著者に **方条ゆとり**(綿流し編・目明し編の作画者)が誤混入 → NDL責任表示「鈴羅木かりん 作画」で是正。

### ★掲載誌が20頁ぶん誤っていた(種3 AI fill)
`monthly-shonen-magazine`(講談社!)が解 皆殺し編に、`shonen-ace`が月刊コンプエース作品に、
`manga-action`が月刊アクション作品に、等。`magazine-corrections.yml` で全て是正。
そのために `data/magazines.yml` に7誌追加: `gangan-powered` `gangan-wing` `gangan-joker`
`gangan-online` `big-gangan` `young-ace-up` `monthly-action`(55→62誌)。
★**月刊コンプエース≠月刊少年エース / 月刊アクション≠漫画アクション / ガンガンパワード≠月刊少年ガンガン** は別誌。

### ★promote のバグを1件直した
**予約頁(preorder-pages)が magazine-corrections を通らない**ため、新規4頁の magazine が空のままだった。
2026-08-03 に同じ型(ジャンルseedが予約頁に届かない)を直した箇所のすぐ上に追加。
= **本流の決定点(種2経由)にある処理は、予約頁の合流路にも要る**という型。他にも同種の穴が残っている可能性。

### 未決
- ★`higurashi-no-nakukoro-ni`(**無印slugを占有**)= 宙出版ツインハートコミックスの**アンソロジー**
  『ひぐらしのなく頃に ～the Nth case～』の第5,6,10,11,12巻。著者30名・欠番だらけ。
  題に「アンソロジー」の語が無いため promote の DROP パターンをすり抜けている。掲載対象外だが**頁削除**なので裁定待ち。
- Wikipedia漫画一覧にあって未登録: **ひぐらしデイブレイクPortable**(綾見ちは・云熊まく) /
  **ひぐらしの哭く頃に 雀**(同) / **雀 -燕返し編-**(山田J太・竹書房) / **デイブレイクPortable MEGA EDITION**(ひらふみ)。
  題が「ひぐらしのなく頃に」でないため今回のTSVに含まれず書誌未収集。
- `ひぐらしのなく頃に煌 妖戦し編(努)`(9784803002775・アース・スター 2011)= **著者がNDL・楽天とも空**で登録保留。
- 掲載誌が空の8頁(奇譚撰集/新奇譚集/板垣ハコ撰集/マジキュー4コマ/恋映し編/なく恋に/雛見沢停留所/今日のひぐらしさん)は
  Wikipedia漫画一覧に無く外部権威が取れないため**空のまま**(推測で埋めない)。

関連: [[magazine_corrections_mechanism]] [[edition_canonical_mechanism]] [[anthology_consolidation_state]]
