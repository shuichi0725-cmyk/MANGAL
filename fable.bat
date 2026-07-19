@echo off
rem MANGAL: resume Claude with full context, no permission prompts.
rem Usage: double-click in Explorer, OR in PowerShell run:  .\c
cd /d "%~dp0"
claude --continue --model "fable[1m]" --dangerously-skip-permissions %*
