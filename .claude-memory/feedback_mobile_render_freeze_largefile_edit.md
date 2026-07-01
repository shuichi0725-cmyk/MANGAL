---
name: feedback-mobile-render-freeze-largefile-edit
description: モバイルapp で巨大ファイル(33MB series-supplement yml)への Edit カード以降が描画されなくなる。大ファイル操作後は短文を挟む/出力を小さく保つ
metadata:
  node_type: memory
  type: feedback
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

2026-05-30、 ユーザのモバイルapp で **`data/seeds/series-supplement-v2.yml`(33MB)への Edit tool カードの後、 それ以降のメッセージ・tool 結果が一切描画されなくなった**(スクショ2枚で確認 = 末尾「Edit >」より下が空白)。 ユーザ報告「edit のあと何も表示されなくなった」。 選択肢 UI ([[feedback_no_askuserquestion_ui]]) とは**別の描画バグ**。

**Why:** 巨大ファイルへの Edit / 大きな Read / 大ペイロードの tool カードが trigger と推測。 描画が止まっても**サーバ側の処理・commit は正常完了している**(バツ＆テリー fill = commit 66c6b02 は成功していた)= データ破損ではなく**表示のみ**の問題。 ただし出先では「止まった」ように見えて操作不能=致命的。

**How to apply:**
1. **巨大ファイル(特に series-supplement-v2.yml 33MB)への Edit/大Read の直後に、 短いテキスト1行を必ず送る**(新しい描画ブロックで復帰しやすい)。
2. tool 出力を**小さく保つ**(全文 parse ログ・巨大 diff・長大な sed 出力をそのまま流さない。 tail で絞る/件数だけ報告)。
3. 大ファイル操作は**小さなチャンクに分割**。 1メッセージに大カードを複数積まない。
4. 重要な完了状態(commit hash 等)は freeze で見えない可能性を前提に、 **次の短い turn で再掲**して確実に届ける。
