---
name: wikipedia-bibliography-crosscheck
description: 【手法】ユーザがWikipedia URLを貼ったら、書誌情報節を機械parseして版ごとに全冊突合する。ISBN無しの記事でも「全何巻」が効く
metadata: 
  node_type: memory
  type: reference
  originSessionId: fa3eed2c-bf86-4ffe-b701-6b416a249bdb
  modified: 2026-09-06T06:53:15.914Z
---

★2026-09-06 確立。ユーザが作品のWikipedia URLを貼ってきたら**この手順で全冊突合**する(巻抜け調査の最短路)。

## 取り方
`curl "https://ja.wikipedia.org/w/api.php?action=parse&page=<URLエンコード題>&prop=wikitext&format=json"`
(WebFetch不要・robots問題なし)。`== 単行本 ==` と `== 書誌情報 ==` の2節を見る。

## 2種類の使い方
1. **書誌情報節がある大作**(ブラック・ジャック型): 版ごとに `*# 発売日 {{ISBN|4-253-…}}` の行が並ぶ。
   ISBN-10→13に変換して本番頁のISBN集合と差集合を取ると、**版ごとに何冊足りないか**が機械で出る。
   実例= BJの豪華版シリーズ全17巻に対し当方16巻(15巻 9784253099837 が欠落)を発見。
   他5版(SCC25/全集22/秋田文庫17/新装版17/文庫全集12)は**全冊一致**だった。
2. **ISBNが無い古い作品**(ロック冒険記型): 単行本節に**版ごとの「全何巻」**だけが載る。
   ISBN以前(〜1980)は**これが全巻数の唯一の根拠**。→ ①どの版が初出か(通常版タブに据える版)
   ②当方の保有数との差=真の欠落か ③割れているレーベルの正しい巻数 ④頁に出ていない版の実在確認、が判る。

## 注意
- 突合後に残る差は**設計どおりの非掲載**であることが多い: 他作者のスピンオフ(別頁)/再編集本・抜粋本/
  資料本(ガイド・Treasure Book)/コンビニ廉価版。差=欠落と即断しない。
- 日付は書かれていないことも多い。**推測で埋めない**([[feedback_accuracy_is_the_goal]])。
- 発売日を採用する時のゲートは [[wikipedia_release_date_is_authoritative]](楽天との2ソース)。
