---
name: process-kill-commandline-self-match
description: 【罠】Win32_Process の CommandLine を正規表現で探して Stop-Process すると、その文字列を含む自分のBashツールのシェルまで殺す(exit 255で以降の行が未実行)。Name で絞り、自分のコマンド行に載る語で探さない
metadata: 
  node_type: memory
  type: reference
  originSessionId: bfd1bf84-8e24-4963-87bc-f48e87455701
  modified: 2026-09-02T10:56:02.294Z
---

2026-09-02 実踏: デタッチ起動した `_weekly-step1.py` を止めようと
`Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '_weekly-step1|_wkstep1' } | Stop-Process`
を Bash ツールから実行 → 一致対象に **自分自身の bash.exe(コマンド行にその正規表現を含む)** が入り、
自分のシェルごと終了(exit 255)。同じコマンド内の後続(ps1書換・再起動・確認)は**1行も実行されない**。

**How to apply**:
- 殺す側は `$_.Name -eq 'python.exe'`(または node.exe)で先に絞り、そのうえで CommandLine を見る。bash.exe/powershell.exe は対象にしない。
- 探す語は自分のコマンド行に載らないもの(ps1ファイル名の一部は載るので不可)。列挙→目視→PIDでStop-Process の2段が安全。
- 起動前の二重起動チェックも同じフィルタで(`Name -eq 'python.exe' -and CommandLine -match 'weekly-step1'`)。
- 生死判定は MSYS の ps でなく `tasklist //FI "IMAGENAME eq python.exe"`([[long_job_ops]] の既知事項)。

関連: [[bash_tool_heredoc_quote_pitfall]] [[weekly_rehearsal_2026_09_02]]
