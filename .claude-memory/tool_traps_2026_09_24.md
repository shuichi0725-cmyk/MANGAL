---
name: tool_traps_2026_09_24
description: 【道具の罠】_verify-kana-pending.py は --help を解釈せず本番照合が走る / reflect の減少検出の詳細は stderr=grep で絞ると消える / Windowsで書いた一覧はCRLF=cp等のシェルで壊れる
metadata:
  type: feedback
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
