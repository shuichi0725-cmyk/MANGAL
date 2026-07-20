@echo off
rem MANGAL: resume Claude (Fable 5 / 1M) with full context, no permission prompts.
rem 旧名 c.bat (2026-07-19 モデル名にリネーム)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\fable
rem ★--continue は「同フォルダの最新セッション」を再開する(前回ログを戻す)。
rem   継続セッションが無い/エラーの時は errorlevel 1 で新規セッションにフォールバック
rem   (opus.bat と同じ保険。これが無いと初回や掴み損ねでウィンドウが即閉じる)。
cd /d "%~dp0"
claude --continue --model "fable[1m]" --dangerously-skip-permissions %*
if errorlevel 1 claude --model "fable[1m]" --dangerously-skip-permissions %*
