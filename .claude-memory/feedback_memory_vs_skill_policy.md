---
name: feedback_memory_vs_skill_policy
description: 【方針】記憶=事実・実測・戒め(無圧縮で保持・巨大化は資産)。やり方=skillが唯一の正(memoryに手順を書かない)
metadata:
  node_type: memory
  type: feedback
---

# 記憶とskillの棲み分け (2026-07-04 ユーザ裁定)

**Why**: やり方がskillとmemoryの両方にあると、更新が片方に入って食い違い、弱いAIはどちらを信じるか迷う。一方、戒め・実測・事故史は圧縮すると文脈が失われる。

**How to apply**:
- **戒め(feedback)・注意点・実測・事故史・データ実体** → memory。圧縮不要、巨大化は必要経費・資産。
- **手順・トリガー運用・コマンド列(やり方)** → `.claude/skills/` が唯一の正。memoryには書かない。既存memoryにやり方が居たらポインタ化して skill へ移す。
- skill化済みのやり方を将来 memory に書きそうになったら、skill 側を更新する。
- 新しい教訓が出たら: 事実は memory・そこから導く運用は skill、に分けて両方更新。
