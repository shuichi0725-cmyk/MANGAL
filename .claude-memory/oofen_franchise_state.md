---
name: oofen_franchise_state
description: 【preview確認待ち】魔術士オーフェン全9頁の見直し状態。本編canonical是正+欠落3作を新規登録(preorder-pages自己完結頁)
metadata: 
  node_type: memory
  type: project
  originSessionId: 164c5cf9-b3fb-40f8-a19c-7cc4f6403843
  modified: 2026-08-07T09:54:56.650Z
---

2026-08-07 ユーザ「魔術士オーフェン 見直してほしい」→ Wikipedia基準で franchise 全体を点検。

## 直したもの
- **本編 `majutsushi-oofen-haguretabi`** = 6巻(沢田一/原作 秋田禎信)に edition-canonical で再構築。
  ★根因= 頁が種2の **誤ったクラスタ**(`name:秋田禎信|name:魔術士オーフェンはぐれ旅` = sid 119689)に紐付いており、
  そのsidが**別作『我が命にしたがえ機械』の巻**を抱えていた。
- **プレ編** = 著者 雀葵蘭 を追加。
- ★`majutsushi-oofen-hagure-tabi`(qid的に正しい5巻クラスタ)は page-dedup で消されていた=本編頁が残る側。

## 新規登録3頁(★種2を通さない `data/seeds/preorder-pages/*.yml` 自己完結頁)
種2が上記のとおり巻を取り違えて収容しており **正しい series が存在しない**ため、SRC `_skey` 結線を使わず自己完結頁にした。
- `majutsushi-oofen-haguretabi-waga-mei-ni-shitagae-doll` 我が命にしたがえ機械 上下2巻(9784047350496/502, 2018-03-28)
  ★題ヨミ= NDL transcription が **ワガ メイ ニ シタガエ ドール**(「機械」の official 読み=ドール)。
- `majutsushi-oofen-haguretabi-waga-mune-de-nemure-bourei` 我が胸で眠れ亡霊 1巻(9784047353169, 2018-11-15)
- `majutsushi-oofen-haguretabi-parody-special` ぱろでぃスペシャル 1巻(9784047122246, 2000-02-29・書影noimageで無し)
  ★保留していた理由(NDL題=魔術士/楽天題=**魔術師**)は**楽天の誤植**と確定。著者は NDL=草河遊也 / 楽天=沢田一 で
  食い違うが、既刊『パロディ大入袋』(9784047122024)も**同じ食い違い方**をするパロディ集の座組なので両名 artist 併記。

## 罠(再発しうる)
- ★preorder-pages の `original_authors` の role は **writer**。`original_author` と書くと reflect-targeted の
  検証ゲートが push を止める(許容= writer/artist/writer_artist/editor)。
- ★reflect-targeted の preview 同期は「**すでに .preview-data に在る頁**」しか上書きしない。
  新規頁を preview に出すには `cp data/manga.v2/<stem>.yml .preview-data/manga/` + `_build-list-index.py` が要る。

## 状態
preview に オーフェン **9頁セット**投入済み(本編/無謀編/MAX/プレ編/大入袋/ぱろでぃスペシャル/獣/機械/亡霊)。ユーザ確認待ち。

関連: [[edition_canonical_mechanism]] [[new_manga_registration_order]] [[preview_deploy_pitfalls]]
