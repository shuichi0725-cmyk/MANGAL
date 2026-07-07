---
name: feedback-mobile-permission-hang
description: スマホから「常に許可」を押すとClaudeが止まりシェル決定待ちになる。再開はc.batで
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

スマホ(Android リモート操作)から権限プロンプトの「**このセッションでは常に許可**」を押下すると、 ★**Claudeが止まってシェル側から決定しないと進まない**ことが多発する。 ユーザはこれに気付いてから、 ★**当セッション中は「常に許可」系を一切選ばない**運用にし、 結果止まらなくなった。

**How to apply**: 権限まわりで「常に許可を押してもらえば無音化する」と**安易に案内しない**(モバイルでは逆に詰まる)。 プロンプトを根本的に消したい時は ★**再起動して文脈ごと再開**を案内する。 そのためのランチャを `mangal/c.bat` に設置済(`cd /d %~dp0` でフォルダ固定 → `claude --continue --dangerously-skip-permissions`)。 = フォルダで `c`(PowerShellは `.\c`)or Explorer ダブルクリックで、 ★この会話を引き継いだまま全プロンプト無効で再開できる。 関連: [[feedback_no_askuserquestion_ui]] [[feedback_mobile_render_freeze_largefile_edit]]。

**2026-07-07 追記(恒久化+新しい罠)**:
- ★恒久化済: `.claude/settings.local.json` に `permissions.defaultMode: "bypassPermissions"` を設定(2026-07-07)。 c.bat フラグ無しの起動でもバイパスで立ち上がる。
- ★新しい罠: **スマホの入力欄横モードバッジをタップしてモードを変える(例=編集を承認/acceptEdits)と、セッション上書きが掛かり設定の bypass より優先**→全ツールで許可プロンプト噴出(タッチ作業で実発生)。 復旧=バッジ再タップで「チェックをバイパス」選択 or c.bat 再起動。 案内=**モードバッジは触らない**。
