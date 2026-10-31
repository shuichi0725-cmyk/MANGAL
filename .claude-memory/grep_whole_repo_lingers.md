---
name: grep_whole_repo_lingers
description: リポジトリ全体の grep -r は2分で終わらず裏に回り40分以上居座る(ユーザが画面で気づく)。範囲を絞るか timeout を付ける
metadata:
  type: feedback
---
`grep -rn … .`(リポジトリ全体)は data/manga.v2 7万頁+キャッシュを舐めて2分のタイムアウトを越え、
バックグラウンドに回って**42分動き続けた**(2026-10-31 ユーザ「なんかタスクが動いてるよ?」)。

**Why:** タイムアウトしたコマンドは自動で背景タスクになり、結果を使わなくても止まらない。

**How to apply:** 探索は `data/seeds docs/production-diagnostics` 等に範囲を絞り、`timeout 100 grep …` を付ける。
頁の存在は `_exists.py`、slug の参照は索引で引く。背景に回ったら使わない時点で TaskStop する。
