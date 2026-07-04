---
name: promote_hangs_on_exit_windows
description: 【事実】promoteはWindowsで完了後もプロセス居座り。完了判定と対処のやり方は skill long-job-ops が正
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★対処のやり方 = **`.claude/skills/long-job-ops/SKILL.md`**(完了判定は成果物とログ末尾・プロセスを待たずkill)。

## 事実の記録
- `_promote-bulk-v2.py` は全yml+art-books書き終え後もプロセスが終了しない(1.9GB級で居座る)。処理は完了済み。
- 完了サイン: ログ最終「→ ...art-books.v2」/ 出力ファイル数。next build も同様に node が居座ることがある(✓ Exporting (2/2) が完了サイン)。
