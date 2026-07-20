@echo off
setlocal
rem MANGAL: Claude (Fable 5 / 1M) を「前回のfableログ」から再開 + Remote Control 自動接続。
rem ★旧junction方式(MANGAL-fable等)は claude の cwd realpath化で無効と判明(2026-07-20)
rem   → モデル別resume方式に全面変更。3bat共通の仕組み:
rem   _session-latest.py が「最後のassistantメッセージが該当モデル系」の最新セッションを特定
rem   → --resume で復元 + --remote-control <名前> で /rc 相当を起動時から自動接続。
rem   見つからない/resume失敗時は新規セッションにフォールバック(=必ず立ち上がる)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\fable
cd /d "%~dp0"
set "SID="
for /f %%i in ('python scripts\_session-latest.py fable') do set "SID=%%i"
if not defined SID goto new
claude --resume %SID% --remote-control fable --model "fable[1m]" --dangerously-skip-permissions %*
if not errorlevel 1 goto :eof
:new
claude --remote-control fable --model "fable[1m]" --dangerously-skip-permissions %*
