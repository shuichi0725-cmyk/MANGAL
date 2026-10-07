---
name: tool_traps_2026_09_24
description: 【道具の罠】_verify-kana-pending.py は --help を解釈せず本番照合が走る / reflect の減少検出の詳細は stderr=grep で絞ると消える / Windowsで書いた一覧はCRLF=cp等のシェルで壊れる
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5d93aabc-75cf-43e0-a92b-5334983246ac
  modified: 2026-10-03T15:26:38.376Z
---

2026-09-24 に実踏した3つ。
- `scripts/_verify-kana-pending.py --help` → **argparse が無く照合本体が走った**(pending 86件をNDL照合)。
  使い方を知りたい時は `--help` を打たず、skill(daily-distill 手順8)か先頭の docstring を読む。未知の引数を無視して本処理に進む script は他にもありうる。
- `_reflect-targeted.py` の「★減少検出」の**明細(消えたISBN/版)は stderr**。`2>&1 | grep '減少'` だと見出しだけ残り明細が消える。
  減少が出たら `sed -n '/減少検出/,/検証ゲート/p'` で丸ごと見る。反映前の控えは自分で取る(反映後は再実行しても差が出ない)。
- Python(Windows)で書いた stem 一覧は CRLF → `for s in $(cat f)` や `cp` で `\r` 付きになり失敗する。`tr -d '\r'` を通すか、Python で完結させる。

**Why:** どれも「動いたように見えて中身が違う」型で、気付くのが遅れる。
**How to apply:** 初めて使う script は実行前に中身(argparse の有無)を読む。減少検出は必ず明細まで読む。
関連: [[feedback_sanity_check_tool_warnings]]
- ★(09-25) `_gen-tameshiyomi-map.py` は **slug-overrides を読まない**= slug改名後も試し読みmapが旧slugキーのまま→改名頁から試し読みが消える。改名したら `tameshiyomi-booklive.jsonl` と `-volumes.jsonl.gz` の slug を新slugへ再キーして map を再生成(finder 16頁で実施)。`_apply-slug-kana-loanword.py` はこれをやらない。
- ★(09-25) `_reflect-targeted.py` の「slug変更検知 → 旧slug索引purge」は **SRC stem のキーしか消さない**。同じ頁を2度改名すると
  (faindaa-no-hyouteki → finder-no-hyouteki → finder-series)、**1つ前の公開slugの行が索引に残る**=検索に旧頁が2重に出る。
  改名後は `python -c` で索引の該当prefixを確認し、残っていれば `_build-list-index.py data/manga.v2 data --remove <旧公開slug>`(preview も)。
  `_gen-redirects.py` の「★WARN alias のキーが公開slug」がこの症状の検出信号。
- ★(09-25) page-dedup.yml は promote が **SRC stem** で照合する。公開slugで書くと改名頁では黙って効かない(人魚の傷で実踏)。
  既存の同型は drop/canonical 両方生きている組が9組(ayashi/daichouhen-doraemon/desire/kibando/pocket-monster-special/
  ten-yori-takaku/to-heart/tobidase-doubutsu-no-mori/yami-no-ekusasaizu)。★09-25 全裁定済: 3組drop(SRC stemで再登録)・6組は別作品=古いdedup行を退役。
  **一律に override 照合へ変えると別作品を消す**(退役前の状態だった)。
- ★(09-25) `_reflect-targeted.py --drop` は pending-r2-prune.jsonl に **SRC stem** で自動追記する。R2のフォルダ名は公開slug=効かない行。
  drop 後は公開slugで手追記し、stem 行は取り消す。根は「--drop が公開slugを知らない」(索引の残骸行と同根)=スクリプト修正は未決(ユーザ判断待ち)。

- ★2026-10-01 追記: `scripts/_catch-audit.py --drop/--fix` は catch-ja.json を `indent=1` で書き戻す。本体は区切り詰め(compact)の1行JSONなので、使うと全行差分になる。キャッチの撤回は compact (`separators=(',',':')`) で自前に書き、manga-catch-index.json(公開slugキー)も同時に消すこと。`_synopsis-audit.py` は synopsis-ja.json がもともと indent=1 なので問題なし。
- ★同日: AniList 番号を共有する頁群(244群・539頁)のうち、題に続編系の語を含む19群を AniList 原文で裁定し、別作品8頁を edition-overrides `"anilist": false` で遮断した。和訳あらすじ(synopsis-ja)には訳語誤り(Akira Hio→聖悠紀、Asuna→安孫子)と混成文(佐藤君=2作品の合成)の型もあった。[[catch_side_wrong_work_class]]
- ★(10-03) **`--help` で本体が走る型をまた踏んだ**: `_preorder-apply-zokkan.py --help` = 本処理が再実行され `zokkan-touched.json` を**空で上書き**(種4の差分から復元)。
  → 引数解析の無い予約系10本に `-h/--help` ガードを入れた(docstring を出して終了)。他の script は未対策= 引き続き先に中身を読む。
- ★(10-03) `_apply-preorder-date-drift.py --apply` を2回 → override 台帳に同じ7行が二重追記(監査TSVが古いまま同じ候補が残る)。→ (isbn13,date) 既在は書かないよう冪等化済み。
- ★(10-03) Bash の heredoc で Python に正規表現を書き込ませたら、`\b` がバックスペース文字(0x08)として書かれた(grep の表示では見えない)。
  **正規表現の行は Edit ツールで書く**。書いた後は `od -c` か `open(p,'rb').read().count(bytes([8]))` が 0 かで確かめる。

## ★罠(2026-10-04 実踏): data/manga.dryrun は git 追跡(69,474ファイル・6/14 ddf1ace12)
- `_promote-bulk-v2.py --dry-run` の出力先 = data/manga.dryrun = **追跡済み**。検算後に `rm -rf data/manga.dryrun` すると
  次の `git add -A` で6.9万ファイル削除がコミットに混ざる(fe06786df で実踏 → 6caec3b9f で復元・ツリーハッシュ一致確認)。
- **消さない**。検算後は `git checkout -- data/manga.dryrun`(+`git clean -fd data/manga.dryrun`)で戻す。
  コミットは `git add -A` を避け、触ったパスを名指しで add する。commit 後に `git show --stat HEAD | tail -1` で件数を見る。
- ★(10-08) `_promote-bulk-v2.py --dry-run --only <slug>` は**予約頁(preorder-pages)2,318頁を全部** `data/manga.dryrun/` に書き出す
  (予約合流は --only を見ない)。`data/manga.dryrun/` は **git追跡ディレクトリ**(69k)= 試し生成の後は未追跡の新規を消し、
  変わった追跡ファイルは `git checkout` で戻す(放置すると次の `git add data` で巻き込む)。
