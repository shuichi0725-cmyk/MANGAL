---
name: special_edition_fix_state
description: 【進行中・残3タスク】特装版混入の是正(通常版主+特装variant併存=案B)。種1 schema:versionが版名権威。(a)418+(b)230=648巻適用済。残=none第2パス/41書影/別フォーマット4396
metadata:
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-17 実施。標準版に**特装版/限定版ISBNが紛れて通常版面で出る**問題(ベルセルク41-43/化物語型)を是正中。

## 確立した方法(再利用)
- ★**種1(MADB metadata101.json)の `schema:version` が版名の権威**(タイトルには出ない。例 schema:version="キャンバスアート&ドラマCD付き特装版")。`schema:price`/`schema:datePublished`/`schema:size`も有用。
- ★**判別**: おまけ特装/限定 = 通常版と**同月発売(0ヶ月)・価格1.8倍**(実証済)。別フォーマット(新装/完全/文庫)=**10年後・同価格** → 別問題。
- ★**通常版ISBNの取得2系統**: (a)種1に同巻・version無し兄弟あり=種1完結 / (b)兄弟なし(化物語型)=楽天で特定(著者検索+巻番号[全角括弧優先]+題名コア一致+ISBN近接で確証。だろう運転禁止[[merge_needs_external_proof]])。
- ★**書影**: 楽天検索は在庫品しか返さないが、**画像CDNは構築URLで在庫切れでも取れる**: `thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/<ISBN下4桁>/<isbn>.jpg?_ex=200x200`(suffix _1_2/_1_4 も試す。HTTP200+image+>2KBで実在確認)。
- ★**表示=案B**: 通常版を主(isbn/cover/date差替)、特装版は `volumes[].variants[]`(label/isbn13/cover_url/price)で併存。schema追加済。詳細パネルに楽天/Yahoo/Amazon3ボタン。

## 適用済(本番manga.v2 + .preview-data/manga、テストpush済)
- **(a)種1完結 418巻/約230作** + **(b)化物語型 230巻/107作** = **計648巻**を是正。
- 履歴(git): `data/seeds/special-edition-fix.yml`(a定義) / `special-edition-fix-b.yml`(b high225) /
  `special-edition-fix-b-review.tsv`(b med14+none555) / `special-edition-fix-changelog.jsonl`(累計884行) /
  scripts: `_special_edition_fix_gen|covers|apply`(--seed対応) / `_sef_construct_covers` / `_sef_b_scope|match`。
- ★manga.v2はgit非追跡=seedから再適用可。適用は special_isbn一致で冪等。バックアップ `.cache/manga.bak-sef-*`。

## ★取り直し済(2026-06-18, outOfStockFlag=1 + マッチャ4バグ修正)
- [[rakuten_out_of_stock_flag]] 発覚後、`_sef_redo.py`/`_sef_redo2.py` で取り直し。累計 **約1,119巻**是正((a)418 + (b)230 + redo365 + redo2_84 + 化物語22)。changelog 1,400+行。
- ★ユーザ指摘で直したマッチャの**4バグ**(毎回ユーザが正しかった):
  1. 楽天は既定で在庫切れ除外 → `outOfStockFlag=1`
  2. 巻番号パーサが「題名␣数字」(全角空白)形式を拾えず
  3. 検索作品名に「【特装版】」が残り特装版しか返らず
  4. 巻番号を“パース”せず**既知の目的巻番号をトークン照合**に変更(レーベル併記等に対応)
- ★楽天は **~1 req/sec 厳守**(1.0秒。+0.1は~10%無駄)。

## ★最終(2026-06-18): 本番manga.v2 是正 = 1,133巻(distinct) / 残98
- NDL仕上げ(`_sef_ndl_finish.py`: NDL ndc=726→通常版ISBN→楽天書影)で+19。changelog target=manga.v2 distinct = **1,133巻**。
- ★残98 = `data/seeds/special-edition-fix-final-remaining.tsv`。**ほぼニッチBL/成年(茜新社/ダリア/一迅社/リブレ等)＋「初回版」**=通常版が存在しない初回特典版 or 一般流通外(NDL ndc=726・楽天とも未掲載)。**自動ヒューリスティックは打ち止め**=個別手動 or 据え置き(special-only)が妥当。
- 教訓: 楽天もNDLも **title検索が我々のDB題(英語/。付き/副題)に当たりにくい**+上/下巻・同梱物名で照合が外れる、が長い尻尾の主因。ISBN点照会は確実だが通常版ISBNが未知という鶏卵。

## (旧)残117(楽天マッチ未到達=データは在る)= NDL案件
- 38=楽天Books未収録(ニッチBL/成年・茜新社/イーストプレス等)。79=**上/下巻・同梱物名・スピンオフ副題**で検索/照合が外れる。台帳 `special-edition-fix-redo2-review.tsv` / `.cache/genre-rakuten/sef-remaining.tsv`。
- ★楽天のタイトル表記が無秩序でヒューリスティック抽出が限界 → **NDL(dcndlで巻番号・ISBNが構造化フィールド=タイトル解析不要)が本筋**。ただし初回NDLプローブはwork単位レコードでISBN取得できず=NDL SRUのmanifestation/recordSchema追加調査が要る。

## ★残タスク(更新)
1. **未マッチ 201巻**(redo後の残)= 楽天に通常版が真に無い/特装のみ刊行の疑い。台帳 `special-edition-fix-redo-review.tsv`。NDLで最終確認。
2. **(b) high の variant 価格 None** = (b)初回は種1価格(空)を使った分。楽天(outOfStockFlag=1)で variant 価格を埋める軽パス未実施。
3. **別フォーマット版 4,396巻**(新装版2104/完全版752/愛蔵版370/文庫/ワイド…)= standard混在 → **版タブ分離**の別設計([[multi_edition_unification_pending]])。おまけ特装と混同しない。
4. (別件)home「今月の新刊」棚が `coverUrl()`=vol1優先で**全部1巻表紙**になる→新刊巻の表紙にする小修正(未)。

## 恒久策(intake側・未実装)
- promoteで「standardに `schema:version`=特装/限定 が来たら variant化、別フォーマットは別edition化」して**今後の流入を止める**。種1 version を読むだけ。
