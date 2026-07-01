---
name: gdrive-code-folder-only
description: 【厳守】Google Driveは「code」フォルダのみ読み書き可。それ以外は一切読み書き禁止(ユーザ明示指示 2026-06-13)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

Google Drive 連携(claude.ai Google Drive MCP、Androidアプリから認証済み・2026-06-13接続)の利用範囲:

- **「code」フォルダのみ読み書きしてよい**
- **それ以外のフォルダ/ファイルは一切読み書きしない**(検索で他フォルダが引っかかっても開かない)

**Why:** ユーザの個人Driveアカウントに直結しており、code以外は私用領域。明示指示(2026-06-13)。

**How to apply:** Drive操作は常に code フォルダ配下に限定。検索クエリもなるべく code 内に絞る。範囲外のファイルが必要に見えても、ユーザに依頼して code に置いてもらう。

接続の注意: MCPツールはセッション開始時に読み込まれる=接続後の既存セッションでは見えない(c.bat再起動で有効化)。
