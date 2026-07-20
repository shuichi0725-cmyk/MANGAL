@echo off
rem MANGAL: resume Claude (Fable 5 / 1M) with full context, no permission prompts.
rem 旧名 c.bat (2026-07-19 モデル名にリネーム)。
rem Usage: double-click in Explorer, OR in PowerShell run:  .\fable
rem ★MANGAL-fable(=MANGALへのjunction)で起動する: セッション名前空間を分離し、
rem   MANGAL直下で走る opus 等 別モデルのセッションを --continue が掴む事故を根絶
rem   (2026-07-20。opus.bat=MANGAL-opus / sonnet.bat=MANGAL-remote と同型)。
rem   実体は同一repo・skills/CLAUDE.md/memory(junction共有)も同じ。
rem ★--continue は「同フォルダ(=fable名前空間)の最新セッション」を戻す。
rem   継続セッションが無い/エラー時は errorlevel 1 で新規にフォールバックし必ず立ち上がる。
cd /d "C:\Users\chiba shuichi\code\MANGAL-fable"
claude --continue --model "fable[1m]" --dangerously-skip-permissions %*
if errorlevel 1 claude --model "fable[1m]" --dangerously-skip-permissions %*
