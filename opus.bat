@echo off
rem MANGAL: run Claude (Opus 4.8 / 1M) as an independent session, no permission prompts.
rem fable.bat と同時併用できる (2026-07-19 新設)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\opus
rem ★MANGAL-opus(=MANGALへのjunction)で起動する: セッション名前空間を分離し、
rem   fable.bat / opus.bat の --continue が互いのセッションを掴まないようにする。
rem   実体は同一repo・skills/CLAUDE.md/memory(junction共有)も同じ。
rem ★初回だけ継続セッションが無いので --continue が失敗→自動で新規セッションに落ちる。
cd /d "C:\Users\chiba shuichi\code\MANGAL-opus"
claude --continue --model "opus[1m]" --dangerously-skip-permissions %*
if errorlevel 1 claude --model "opus[1m]" --dangerously-skip-permissions %*
