---
name: feedback-no-askuserquestion-ui
description: AskUserQuestion の選択 UI がユーザ環境で表示されない。質問は通常テキストで行う
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

ユーザ環境では AskUserQuestion の選択肢 UI が**見えない** (= 「この選択方式は見えないのでやめて」 2026-05-30)。 ★2026-05-30 再強調: 「見えない時があるし、 今回みたいにより致命的な表示になると出先でどうにもならなくなる」 = **断続的に不可視 + 致命的表示崩れ** で、 出先(モバイル)では操作不能に陥る。 ユーザが「止まっているのかと思った」と誤解する原因にもなる。 → **AskUserQuestion は使用禁止(固定ルール)**。

**Why:** モバイル中心の操作環境 (= [[feedback_askuserquestion_short_labels]] と同根) で、選択コンポーネントが描画されず選べない。 不可視は毎回でなく断続的なので「たまになら可」ではなく**常時テキスト**にすること(出先で詰むリスクが致命的)。

**How to apply:** 確認や選択肢提示は AskUserQuestion を**一切使わず**、**通常のテキスト本文で番号付き選択肢を書いて** 「1で」等の返信を求める。短い label + 本文説明の原則 ([[feedback_askuserquestion_short_labels]]) は維持しつつ、媒体を必ずテキストにする。
