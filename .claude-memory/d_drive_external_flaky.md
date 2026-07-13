---
name: d-drive-external-flaky
description: D:は外付けで最近突然認識が外れる。復旧=ユーザが挿し直すだけ。Claudeはドライブレター探索/変更を絶対しない
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6021a518-a36b-44ff-aa0c-31013be82fed
---

D:ドライブ(mangal-cache、.cache/.next junctionの実体)は**外付けドライブ**で、最近突然認識が外れることがある(2026-07-14実例)。復旧は**ユーザが外して挿し直すだけ**。

**Why:** D:消失時に別レターのボリューム(E:等)を「移動したD:」と推定してSet-Partitionでレター変更を試みたら、ユーザから「Eドライブを探し出すのはやめてほしい」と明確な指摘。ドライブ推定は誤爆リスク(別物のボリュームを掴む)があり、そもそも挿し直しで直る。

**How to apply:**
- D:/.cacheがENOENT等で見えない → **即ユーザに「D:が外れています。挿し直してください」と報告して待つ**。Set-Partition/subst/junction張り替え等の自前復旧は禁止
- 長時間ジョブ(promote/harvest/build)がD:依存で突然死した場合もまずこれを疑う
- 関連: [[promote_hangs_on_exit_windows]] [[feedback_user_directive_supremacy]]
