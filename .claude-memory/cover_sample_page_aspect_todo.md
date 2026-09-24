---
name: cover_sample_page_aspect_todo
description: 【残作業・ユーザ指示「いつか調べる」】楽天の基本書影(.jpg)が表紙でなく本文サンプルページの型を、縦横比で全頁洗い出す。ちいかわ2・4巻で発見・是正済
metadata:
  type: project
---

2026-09-24 ちいかわ 2巻・4巻で発見: 楽天の基本画像 `…/<isbn>.jpg` が**本文サンプルページ**(横長300x163 / 正方形296x300)で、
正しい表紙は `_1_2.jpg`(縦長211x300)だった。cover-override.jsonl で2件是正済み。ユーザ「縦横比をいつか調べるので残作業として覚えておいて」。

## やる時の手順案
- 対象=頁の cover_url(variants含む)。画像を取得し **幅≥高さ(横長・正方形)** を候補に(表紙は縦長 約0.7)。
  取得は重いので、まず頁の代表書影・巻書影を1パスで(並列は控えめ・楽天サムネCDN)。
- 候補ごとに `_1_2`〜`_1_5` を試し、縦長のものがあれば差し替え候補。**目視確認してから** cover-override.jsonl へ
  (reason に旧画像の縦横比を書く)。画集・横長判型の本(本当に横長の表紙)は除外=偽陽性に注意。
- 1件のバグ=型 → 月次サニティ検出器化も検討([[feedback_one_bug_means_a_class]])。
関連: [[cover_resolution_policy]] [[feedback_cover_oddity_signal]]
