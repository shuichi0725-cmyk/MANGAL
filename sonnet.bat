@echo off
rem MANGAL: open a second terminal running Claude (Sonnet) in remote-control mode,
rem so the mobile app can connect to this PC (アイドル運転などをアプリから操作する用)。
rem 旧名 d.bat (2026-07-19 モデル名にリネーム)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\sonnet
rem 既存ターミナルのセッション(fable.bat)とは独立。閉じる時はその窓を閉じるだけ。
rem ★MANGAL-remote(=MANGALへのjunction)で起動する: セッション名前空間を分離し、
rem   fable.bat の --continue が sonnet セッションを掴む事故を根絶(2026-07-18)。
rem   実体は同一repo・skills/CLAUDE.md/memory(junction共有)も同じ。
cd /d "C:\Users\chiba shuichi\code\MANGAL-remote"
start "claude remote-control" cmd /k claude --remote-control --model sonnet --dangerously-skip-permissions %*
