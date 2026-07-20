@echo off
rem MANGAL: 別ターミナルで Claude (Sonnet) を「前回のsonnetログ」から再開 + Remote Control 自動接続。
rem モバイルアプリ操作用(アイドル運転など)。窓を閉じれば終了。
rem 仕組みは fable.bat と同型 (モデル別resume方式、2026-07-20全面変更。旧MANGAL-remote junction廃止)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\sonnet
if "%~1"=="__inner" goto inner
start "claude sonnet" cmd /k call "%~f0" __inner
goto :eof
:inner
setlocal
cd /d "%~dp0"
set "SID="
for /f %%i in ('python scripts\_session-latest.py sonnet') do set "SID=%%i"
if not defined SID goto new
claude --resume %SID% --remote-control sonnet --model sonnet --dangerously-skip-permissions
if not errorlevel 1 goto :eof
:new
claude --remote-control sonnet --model sonnet --dangerously-skip-permissions
