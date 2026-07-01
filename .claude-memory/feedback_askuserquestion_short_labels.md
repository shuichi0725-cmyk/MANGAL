---
name: feedback-askuserquestion-short-labels
description: AskUserQuestion の option label / description は 短く 簡潔に書く (= モバイルで 長文 読めない)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6146d01a-d071-41e5-9ffa-4568e252bbb1
---

AskUserQuestion で 長い option label / 説明文 を 書くと モバイル UI で 読めない / 読みづらい。

**Why:** ユーザは モバイル中心 (= Android リモート操作)。 私が 「Phase 3 = promote 改修 (= 推奨)」 + 詳細 description で 4 option 出した時 = 「全部読めない、 言葉で説明して」 と フィードバック発生。

**再発 (2026-05-29):** 種2作り直しの scope/団体/role を 3問 × 長い description で聞いて、また「字が読めないので止めて」と拒否された。description も長いとダメ = label だけでなく **description も長文は全部 NG**。

**How to apply (強め):**
- label = 4-8 文字 程度 (= 「Phase 3 改修」 「Phase 2 AI」 「両方並行」 「休止」 等)
- description も **短く** (= 1 行 / 30 文字以内、長い背景説明を詰め込まない)
- 多要素の設計判断は ★ AskUserQuestion を**避ける**。代わりに本文で短く要点 → 推奨 default を決めてプランに書き、承認時に方向修正してもらう方式が確実 (= この方式で承認まで進めた)
- どうしても聞くなら 1問だけ・超短文
