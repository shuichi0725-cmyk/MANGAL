@echo off
setlocal
rem MANGAL: Claude (Opus 5 / 1M) を「前回のopusログ」から再開 + Remote Control 自動接続。
rem 仕組みは fable.bat と同型 (モデル別resume方式、2026-07-20全面変更。旧MANGAL-opus junction廃止)。
rem ★2026-07-28: 前回ログが文脈75%超なら resume せず新規起動(起動時の勝手な自動圧縮を回避)。過去ログ=log.bat opus
rem Usage: double-click in Explorer, OR in PowerShell run:  .\opus
cd /d "%~dp0"
set "SID="
for /f %%i in ('python scripts\_session-latest.py opus') do set "SID=%%i"
if not defined SID goto new
claude --resume %SID% --remote-control opus --model "claude-opus-5[1m]" --dangerously-skip-permissions %*
if not errorlevel 1 goto :eof
:new
claude --remote-control opus --model "claude-opus-5[1m]" --dangerously-skip-permissions %*
