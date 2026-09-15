---
name: detached_job_dies_on_session_teardown
description: 【罠・回避策あり】Start-Processでデタッチした長時間ジョブはセッション終了(--resume/再起動)で道連れに死ぬ。WMI Win32_Process.Create なら生き残る
metadata:
  type: project
---

2026-09-15 週次蒸留で実踏。`Start-Process powershell -WindowStyle Hidden -File .cache\_wkbuild.ps1` で
起こしたフルビルドが、**Claude Code 側のセッションが落ちた瞬間に一緒に死んだ**
(45,635/91,271 頁で無音停止・node 0本・ログに FATAL なし・`weekly-build.exit` も未書込)。
22分ぶんが無駄になった。skill weekly-distill の「buildは必ずStart-Processでデタッチ起動」は
**ツールの run_in_background より強い**だけで、**セッション teardown には勝てない**。

## 見分け方(死んだのか無言なのか)

- `@(Get-Process node).Count` が **0** かつ `.exit` ファイルが無い = 死。
- ログ最終更新が数分前で止まっているのも傍証。R2同期は照合フェーズで長時間無言になるが、
  その場合は python が生きていて CPU 時間が伸びる([[long-job-ops]] の生存確認と同じ)。
- ★`out/manga` の枚数は判定に使えない(前週の残骸13.5万枚が残る)。

## 回避策 = ジョブオブジェクトから切り離して起こす

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine='powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\...\.cache\_wkbuild.ps1"';
  CurrentDirectory='C:\Users\chiba shuichi\code\MANGAL'}
```

WMI プロバイダ(WmiPrvSE)の子として起きるので、こちらのセッションが落ちても生き残る。
同日の再ビルド(2.5分コンパイル→41分で完走・EXIT=0)とR2同期はこの方式で通した。
★監視の Monitor はセッション側なので一緒に死ぬ = **ジョブが生きていても監視は張り直す**。
