---
name: slug_duplicated_token_sareta_type
description: 【型・89件是正済】slugに同じ音が二度出る(tsuihousareta-sareta)。漢字のローマ字化と種3 title_kana_segmented の分かち書きが二重に効く。key2slugは切り詰め前のフル長を持つ罠つき
metadata: 
  node_type: memory
  type: project
  originSessionId: 58a222b6-cb74-4572-9905-4dacb5f8ddb9
  modified: 2026-09-10T07:01:56.610Z
---

2026-09-10 実踏。ユーザが `pakupaku-desuwa-tsuihousareta-sareta-ojousama` を見て
「されたされたはなおすべき」と指示 → 型として全掃引し **89件**を一括是正した。

## 型
slug 生成で **漢字側のローマ字化**(「追放された」→`tsuihousareta`)と、
**種3 `title_kana_segmented` の分かち書き**(`ツイホウ サレタ` → `sareta`)が
**二重に効いて** 同じ音が2トークン並ぶ。異世界追放系の量産作品に集中していた。

- 84件 = `…sareta-sareta`(追放された/解雇された)
- 5件 = `…sareta-saretakedo`(「追放されたけど」)

## 抽出ルール(偽陽性を除ける形)
トークン列で **「前が `sareta` で終わり・次が `sareta` で始まる」**。
★素朴な「前トークンの末尾==次トークン」だと **122件**出るが、大半は正当な繰り返しで偽陽性:
`konna-onna`(こんな女) / `kedamono-damono` / `sansan-san` / `switch-witch` /
`taranta-ranta` / `uraniwa-niwa` / `inkosama-sama` …。**題を見ないと切れない**。

## ★key2slug は「切り詰め前のフル長 slug」を持つ
`data/manga.v2` と索引の slug は**最大長で切り詰め済み**だが、
`.cache/apply/key2slug.tsv` の値は**切り詰め前のフル長**。
→ 「値が現 slug と完全一致する行」だけ直すと **89件中59件しか当たらない**。
残り30件はフル長側に `sareta-sareta` が残り、次の `_slug-apply-build.py` で**旧slugへ戻る**。
★key2slug は**全行にルールを適用**すること。

## 移設が要る seed = 59ファイル・延べ2,044箇所
[[slug_rename_kills_slugkeyed_seed]] の通り、公開slugキーの seed を全部移す。実測で効く層:
`catch-ja 84` / **`volume-desc-ja 74`(巻説明)** / **`tameshiyomi-booklive 61`(試し読み)** /
`release-date-fill 237` / `tag-rakuten 36` / `genre-rakuten 16` / `synopsis-slug-ja 17` /
`cover-override 14` / `distill-synopsis` / `anime-adapted-overrides` / `author-overrides` …
★旧slugを**部分文字列に含む別slug**が無いことを先に検査し、**長い順に置換**すれば単純置換で安全
(実測: 包含関係 0)。

## 検算(全部やる)
- reflect の「減少なし」「検証ゲートOK」/ 本番索引の総数が ±0
- **旧→新 301 を全件照合**(欠け0)/ 新slugが索引に在る / **旧slugの残存0**
- alias は ①旧→新を追加 ②**旧slugを行き先にしていた既存alias を最終行き先へ張り替え**
  (死に連鎖の防止。今回61件あった)
- `pending-r2-prune.jsonl` に旧slugを全件

**Why:** 1件の見た目のバグが、量産ジャンル全体に同じ形で広がっていた。
**How to apply:** slug の異常を見たら、まず**題を見て偽陽性を切る規則**を作ってから掃引する。
関連: [[slug_rename_kills_slugkeyed_seed]] [[new_page_creation_srcpage_key2slug]]
[[drop_page_redirect_chain]] [[feedback_one_bug_means_a_class]] [[madb_parallel_title_inversion]]
