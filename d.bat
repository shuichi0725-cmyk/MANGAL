@echo off
rem MANGAL: open a second terminal running Claude in remote-control mode,
rem so the mobile app can connect to this PC (アイドル運転などをアプリから操作する用)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\d
rem 既存ターミナルのセッション(c.bat)とは独立。閉じる時はその窓を閉じるだけ。
cd /d "%~dp0"
start "claude remote-control" cmd /k claude --remote-control --model sonnet --dangerously-skip-permissions %*
