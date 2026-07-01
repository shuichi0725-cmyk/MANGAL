---
name: memory_git_mirror
description: 【必ず使う】記憶は.claude(ローカル)→repo/.claude-memory/へミラーしてgit永続化。記憶更新後は_sync-memory.py+push
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

2026-07-01 ユーザ「GitHubのMEMORY.md更新が止まってる」で発覚した盲点を恒久修正。

## 問題
- Claude標準の記憶 `C:\Users\shuic\.claude\projects\C--Users-shuic-code-MANGAL\memory\`(132ファイル)は**このPCローカル=git管理外**。GitHubにバックアップされず別PC/モバイル不可視。
- CLAUDE.mdは「記憶は別PCでも消えない」と書くのに**実際はgitで担保されていなかった**。
- repo `MEMORY.md`(1,825行手動doc)は5/22で凍結=これは旧・別物。現行記憶は`.claude`側。

## 恒久策(確立済)
- **repo `.claude-memory/` に記憶を鏡写し**(132ファイル・788K)。git追跡=GitHubバックアップ+可視+cross-PC。非破壊(旧MEMORY.mdは残す)。
- **同期スクリプト `scripts/_sync-memory.py`**: `.claude/.../memory/*.md` → `.claude-memory/`(追加/更新/削除反映)。
- ★**運用**: 記憶ファイルを書いた/消したら → `python scripts/_sync-memory.py` → `git add .claude-memory && commit && push`。CLAUDE.md一般protocolにも明記。
- 別PCではSRCパスが違う(各自の.claude)ので`_sync-memory.py`のSRC調整要。

## 現行記憶の正
- **`.claude-memory/MEMORY.md`(索引)＋各mdファイル = 現行の正**。GitHubで見えるのはこれ。
- 旧 repo root `MEMORY.md` は参照用に残置(触らない)。
