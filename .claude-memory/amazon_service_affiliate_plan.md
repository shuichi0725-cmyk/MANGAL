---
name: amazon_service_affiliate_plan
description: 【宿題・GO待ち】Amazonサービス(サブスク)アフィの設計。カート周り5案は提示済み・裁定待ち。/service 頁とヘッダー枠も確保済み
metadata: 
  node_type: memory
  type: project
  originSessionId: a50b5b4d-87c7-41d8-9aa8-1ac1ee503f1d
  modified: 2026-09-08T00:55:48.198Z
---

2026-09-08 着手。**カート周りの導線の形をユーザが「ゆっくり考えたい」= 宿題**。実装は裁定後。

## 何をやるか

Amazonアソシエイトの **メンバー紹介イベント(定額報酬)** を作品頁と `/service` 頁に出す。
商品の売上%とは別枠で、**無料体験の新規登録1件あたり**の固定報酬。

| サービス | 報酬 | 出す条件 | 根拠データ |
|---|---|---|---|
| Audible | **1,500円** | 小説原作の作品 | AniList `source` = LIGHT_NOVEL 2,599 / WEB_NOVEL 363 |
| Amazon Music Unlimited | 1,000円 | アニメ化 | `anime_adapted` 5,346 |
| Amazonプライム(Prime Video) | 500円 | アニメ化 | 同上 |
| Kindle Unlimited | 500円 | 全作品 | — |

- リンクの作り方 = **対象ページのURLに `?tag=<ID>` を付けるだけ**(専用ツール不要)。
  ID = `mangal08-22`(`.env.local` の `NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG`)。
  ★URLが既に `?` を持つ場合は `&tag=`。`dplnkId` 等のAmazon内部IDはタグではない。
- 成立条件 = **同一セッション内で登録完了**(メール確認まで)。既存会員の再訪は対象外。

## 決まっていること

- 置き場所 = 作品頁の **`<VolumeRow />` 直前**(`app/manga/[slug]/page.tsx`)。巻ごとのボタン横は不可
  (187巻の作品で187回繰り返す)。作品単位で1ブロック。
- 専用頁 = **`/service`**(ユーザ裁定C)。Amazon以外(楽天マガジン・電書ストア初回特典等)も入れる前提の汎用名。
  ★**分けない**(薄い頁を複数作るとインデックスされない)。育ったら `/service/<名前>` に分割。
- **同時に出すのは3つまで**。優先= ①アニメ化→Prime Video ②小説原作→Audible ③アニメ化→Music Unlimited ④全作→KU。
- **月額を静的に書かない**(改定される。KU=980円/月・初回30日無料 は変わりうる)。「初回30日無料」まで。
- **PR表記必須**(ステマ規制)。

## ★裁定待ち = カート周りの見た目5案

比較シート(美味しんぼの実データ・実機幅360px) = https://claude.ai/code/artifact/10f32d3f-e6a2-400e-96d5-f9dd27b89407

A 1行チップ(46px) / B まとめカード(178px) / C 折りたたみ(56px・ほぼ開かれない) /
D ブルータル帯(94px・カテゴリ帯と誤認の懸念) / E 主役1件+残り(108px)

## ★重要な発見: 小説原作の判別は AniList `source`

- 当初 `original_authors`(8,663作)で Audible を出そうとしたが、**これは漫画の原作者**で小説家ではない
  (美味しんぼの雁屋哲が典型)。per作品で出すと嘘になる。
- 正解 = **AniList の `source(version: 3)`**。`.cache/anilist-manga-dump-v3.jsonl.gz`(106,832件)に**取得済み**。
  本番頁と結線した実測 = LIGHT_NOVEL 2,599 / WEB_NOVEL 363 / NOVEL 784。
- ★**NOVEL は使わない**(ユリシーズ/水滸伝/三国志/若草物語。珍遊記=西遊記由来 等、「原作を聴く」が誤誘導になる)。
  使うのは **LIGHT_NOVEL + WEB_NOVEL = 2,962作**。
- AniList結線は現在 **51.3%**(35,504/69,241)なので、結線が進むほどこの数は増える。
- 算出スクリプト = `.cache/_novel_origin.py`(使い捨て。要るなら scripts/ へ昇格)。

## 未確認

- **audible.co.jp は amazon.co.jp と別ドメイン**。題名でAudible内検索へ deep-link するのが
  既存方針(誤マッチ回避)に合うが、**紹介料が計上されるか未確認**。確実なのは `www.amazon.co.jp` の
  Audible登録ページ。まず後者で出し、レポートで計上を確認してから切り替える。
- Kindle Unlimited の言い回し =「この作品が読み放題」は対象変動で言えない。
  暫定「**漫画が読み放題(対象は変動)**」。
- 電子/紙モード切替でアクセントが赤→青に変わる。導線を追随させるか固定か。

## ヘッダーの枠

2026-09-08 に「AI書評→アニメ化 / 過去ログ撤去」を適用済み(`1481abce9`)。
★**本来この空き枠に「サービス(サブスク)」を出したい**というのがユーザの意図。導線の形が決まったら入れる。

[[store_affiliate_architecture]] [[feedback_no_static_prices]] [[anilist_matching_state]]
