---
name: slug-katakana-compound-key-blindspot
description: カナ英語辞書の「複合キー」はjanomeに割られて永久に効かない(オールライト→all light)。直し方2案を本番69,237題で隔離検証して両方却下した記録
metadata:
  node_type: memory
  type: project
---

`data/seeds/katakana-english.yml` に **2語以上が連なった見出し語**(例 `オールライト: all-right`)を足しても**効かない**。`_slug_kana_lib.make_slug` は janome で分かち書きしてから、**カタカナ1トークンごとに** `kata_run_convert` で辞書を引く。janome は「オールライト」を オール+ライト に割るので、複合キーには構造的に一生到達しない。
実害= 『いつかはオールライト』が `itsuka-wa-ooru-light` → 辞書追加後も `itsuka-wa-all-light`(**オール・ライト=光**。意味が変わる)。中黒跨ぎだけは `_nakaguro_dict` が先行置換で救っているが、それはこの穴への部分対処。

★**2026-09-14 に直し方を2案とも試し、本番全題(69,237)で隔離検証して両方却下した**。同じ実験を繰り返さないこと。

1. **題文の先行置換**(カタカナ連の全体が辞書キーなら分かち書き前に英語へ置換) → **却下**。
   英語を差し込むと janome の文脈が変わり、**周辺の日本語の読みが壊れる**。実測386件:
   ヒーローはいかが?→ 助詞「は」が hai / マイペース風太郎→ kaze-tarou / ドラゴン拳→ kobushi。
2. **分かち書き後に連続カタカナtokenを1本の run に結合してから辞書変換** → **却下**。
   3,248題が変化し、改善と退行が混在した。
   改善= tensai-baka-bon→tensai-bakabon / gan-damu→**gundam** / en-dress→**endless** / fan-tomu→phantom。
   退行= gan-frontier→**ganfurontia** / jetto-king→jettokingu / hotto-milk→hottomiruku。
   根因= `kata_run_convert` の**語中マッチ禁止**(buf が非空になったらその run では以降辞書を引かない。
   ブ「ラット」/アクアプ「エラー」誤爆の防止が目的)が、run が長いほど辞書を潰すため。

**Why:** 66k頁の slug を作る装置なので、部分的な改善のために未検証の変更を入れると別の型の退行を量産する。「辞書に足せば直る」は成り立たない箇所がある、と知っておくのが要点。

**How to apply:**
- ★**2案目を本気で採るなら `kata_run_convert` の語中マッチ禁止を同時に設計し直す**必要がある(単純撤廃は誤爆が復活するので不可)。改善386件ぶんの価値はあるので、やるなら独立した作業として。
- ★**隔離検証のやり方**(今回有効だった): lib のソースを読み込み、変更前後の2バリアントを別モジュール名で `exec` し、本番索引の全題に `make_slug` を掛けて差分を数える。「改善/退行」を目で仕分けるまでが1セット。
- 1件ずつ通す正規ルート = `data/seeds/preorder-slug-manual.tsv`(isbn13→slug→根拠)。
  同じ台帳に載せた他の装置限界: `BULLET-バレットー`(英字と同語のカタカナ注記が併記され bullet-bullet になる= [[slug_duplicated_token_sareta_type]])/ `プッシャー天使ケンチー`(ケンチーは人名の造語だが ken-chii に割れる)。
- 辞書に足す前に★**本番の綴り慣行を索引で数える**(既存ルール)。ただし素の件数は割ること: キル は `kiru` 14件に負けて見えるが、中身は**斬る/切る/着るの日本語動詞が12件**で、英語キルは2件。割ると kill 9:2 で英語が優勢 = [[feedback_raw_count_is_not_worklist]]。
- 関連: [[katakana_dict_dead_entry_trap]] [[pending_slug_generator]]
