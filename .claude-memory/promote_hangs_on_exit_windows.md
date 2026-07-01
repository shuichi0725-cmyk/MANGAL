---
name: promote_hangs_on_exit_windows
description: promote(_promote-bulk-v2.py)は処理完了後にプロセスがWindowsで終了ハングする。ログの最終ステップ到達で完了判定しkill。終了通知を待ち続けない
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★**`scripts/_promote-bulk-v2.py` は全yml + art-books を書き終えた後、プロセスが終了せずハングする**(Windows、1.9GB級で居座る)。完了通知が来ないので「動いてない」ように見えるが、**実際は処理は完了済み**。

**完了の判定方法**(終了通知を待たない):
- ログ(`> .cache/xxx.log 2>&1`)に **最終ステップ `→ ...art-books.v2`(or art-books.dryrun)** が出ていれば、manga 本体は全件書き終わっている。
- 出力ファイル数が ~69,474 なら完了(空slug 1件等で 69,506→69,474)。
- 確認後に `Get-Process python | Stop-Process -Force` で kill してよい。

**ハングが招いた二次被害(回避策)**:
- 居座ったゾンビが `manga.dryrun/*.yml` の**ファイルロックを保持** → 次の run の cleanup(unlink)が `WinError 32` で失敗。
- ★対策(実装済): promote の OUT_DIR cleanup は `PermissionError` を5回リトライ + `FileNotFoundError` は skip。空slug(`.yml`)も skip。
- ★運用: 新 run の前に **必ず全 python kill → クリーン確認**。run 中は**ディレクトリを覗かない**(同時アクセスがロック競合を増やす)。完了通知 or ログ最終ステップだけで判断。

**効率(再生成しない)**:
- ★`manga.dryrun` は本番 `manga.v2` と**全く同じ出力**(同コード・同seed)。dry-run 検証済みなら、promote を再実行せず **`manga.dryrun → manga.v2` をコピー/mirror** すれば数十秒で本番化できる(フル再生成=数分を回避)。[[feedback_efficiency_first]]

教訓の本質: **「動いてない」と判断する前に、処理が完了しているか(ログ最終ステップ/ファイル数)を確認する**。プロセス生存 ≠ 処理中。
