@echo off
rem MANGAL: resume Claude (Fable 5 / 1M) with full context, no permission prompts.
rem 旧名 c.bat (2026-07-19 モデル名にリネーム)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\fable
cd /d "%~dp0"
claude --continue --model "fable[1m]" --dangerously-skip-permissions %*
