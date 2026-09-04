---
name: memory-write-to-canonical-not-mirror
description: 【罠・実踏】記憶は正本(.claude/projects/.../memory/)に書く。repo の .claude-memory/ に書いて _sync-memory.py を回すと「正本→鏡」の一方向同期で追記が黙って消える
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b13171da-074b-4da8-a8b5-905f74606a97
  modified: 2026-09-04T11:05:12.577Z
---

記憶ファイルを書く場所は **正本 = `C:\Users\chiba shuichi\.claude\projects\C--Users-chiba-shuichi-code-MANGAL\memory\`**。
repo の `.claude-memory/` は **`scripts/_sync-memory.py` が作る鏡(ミラー)**であって、書き込み先ではない。

**Why:** 2026-09-04 実踏。`.claude-memory/feedback_agent_fanout_token_cost.md` に append →
`python scripts/_sync-memory.py` → `git add .claude-memory && commit` の順でやったところ、
同期が **正本 → 鏡** の方向に上書きするため追記が消え、`git add` は差分ゼロ、
コミットには `_indexnow.py` しか入らなかった。**しかも私はユーザに「記憶に追記して push しました」と報告済みだった**
(= エラーが出ないので気付けない。silent な取りこぼし)。

**How to apply:**
- ★書く順序は **正本に書く → `python scripts/_sync-memory.py` → `git add .claude-memory && commit && push`**。
- ★**書いた後に必ず検算**する: `grep -c "<今書いた見出し>" .claude-memory/<file>` が 1 以上、
  かつ `git show --stat <commit>` に `.claude-memory/` が載っていること。0 なら消えている。
- 鏡側だけを編集したくなったら、それは**書く場所を間違えている**合図。
- 同 script は削除も反映するミラーなので、鏡側で作った新規ファイルも次回同期で消える。

関連: [[memory_git_mirror]] [[feedback_sanity_check_tool_warnings]]
