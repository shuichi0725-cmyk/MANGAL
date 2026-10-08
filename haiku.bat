@echo off
rem MANGAL: start Claude (Haiku 5.5) in a new window, resuming the last haiku session, with Remote Control.
rem For the mobile app. Close the window to end the session.
rem Same mechanism as sonnet.bat and fable.bat: per-model resume via scripts\_session-latest.py.
rem If the last session is over 75 percent of the context window, a new session starts instead.
rem 2026-10-08: model fixed to claude-haiku-5-5. The old id claude-haiku-5-5-20251001 does not exist.
rem NOTE: keep this file ASCII-only with CRLF line endings. cmd.exe on code page 932 misreads UTF-8
rem       Japanese in rem lines and runs fragments of them as commands. Seen 2026-10-08.
rem Usage: double-click in Explorer, OR in PowerShell run:  .\haiku
if "%~1"=="__inner" goto inner
start "claude haiku" cmd /k call "%~f0" __inner
goto :eof
:inner
setlocal
cd /d "%~dp0"
set "SID="
for /f %%i in ('python scripts\_session-latest.py haiku') do set "SID=%%i"
if not defined SID goto new
claude --resume %SID% --remote-control haiku --model claude-haiku-5-5 --dangerously-skip-permissions
if not errorlevel 1 goto :eof
:new
claude --remote-control haiku --model claude-haiku-5-5 --dangerously-skip-permissions
