@echo off
setlocal
rem MANGAL: /clear 等で画面から消えた過去セッションログを notepad で読む(起動し直し不要)。
rem Usage:  log fable        ← fable の最新セッション
rem         log fable 1      ← 1個前のセッション(/clear直後に「消えた方」を見る時)
rem         log opus / log sonnet も同様。引数なし = fable。
cd /d "%~dp0"
set "FAM=%~1"
if "%FAM%"=="" set "FAM=fable"
set "OUT="
for /f "delims=" %%i in ('python scripts\_session-log.py %FAM% %2') do set "OUT=%%i"
if not defined OUT exit /b 1
start "" notepad "%OUT%"
