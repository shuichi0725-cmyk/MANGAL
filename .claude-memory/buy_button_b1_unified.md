---
name: buy-button-b1-unified
description: 買うボタン(Amazon/Kindle/楽天/Yahoo!/Kobo/試し読み)は全箇所 B1「色の立体」= 共通クラス .buy3d に統一(2026-11-19)。新しい買うボタンもこれを使う
metadata:
  node_type: memory
  type: project
  originSessionId: 11c609b3-25f2-4a43-bb64-5ad17edb188e
  modified: 2026-11-18T15:43:03.984Z
---

2026-11-19 ユーザ裁定「全箇所B1形式で置き換えて」(見本 B1〜B6 と 今/B1/B5 比較から選択)。commit 742af6fbf6。**2026-11-20 週次蒸留で本番公開済み**。

- 実体 = `app/globals.css` の `@layer components` に `.buy3d` + 店の色 `is-k/is-a/is-rk/is-yh/is-kb/is-try`、小さい物は `is-sm`(厚み2px)。上から光るグラデ+下に濃い色の厚み(--t)・押すと沈む。Amazon は文字を濃い色(#1a1205)。
- ★spring-press と併用しない(transform 競合)。大きさは utility か各頁 CSS。
- 適用先 9 か所: 作品頁(試し読み/紙の本で買う/電子書籍で買う の3段+小見出し・旧の青い箱は廃止・版の行)、ShinkanRow/EditionRow、BuyButtons(tile/row/mini)、羅針盤 .ck-buy(黒線残す)/.cp-acts-buy/.cp-buytab(付箋は厚み0)、本棚 .shelf-buy-btn、画集(文字リンク→ボタン)、使い方の絵 guide.css。
- 「詳細」ボタンは対象外(据え置き)。VolumeTile/AffiliateLink はどこからも使われていない。

**Why:** ボタンの形が場所ごとにばらばら(四角・丸・漫画線・白地緑枠・青い箱)だったのを統一したいという要望。
**How to apply:** 新しく買うボタンを作る時は `.buy3d is-<店>` を使う。使い方ページの写真は撮り直し対象([[usage_guide_page]])。
