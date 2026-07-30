---
name: smb-share-level-readonly-gotcha
description: "M5_Ultra共有で「見えるが書き込み/削除できない」時はNTFS権限でなくSMB共有レベルの許可を疑う。2026-07-31 D:\本 共有で実際に発生・解決"
metadata:
  type: project
  node_type: memory
---

M5_Ultra([[m5ultra_file_server_setup]])のファイル共有で、フォルダは見える(Read)のに
保存・削除だけ拒否される症状が発生。

**原因**: NTFS権限(icacls)は正常(Authenticated Users:Modify等)だったが、
**SMB共有レベルの許可**(`Get-SmbShareAccess`)がshare1/Everyoneとも **Read のみ** になっていた。
Windowsは NTFS権限とSMB共有権限の**両方をANDして**実効権限を決めるため、
共有側がReadだとNTFS側がModify/Fullでも書き込み不可になる。

**発見の経緯**: `D:\本\一般コミック２` で削除/保存拒否 → icacls(NTFS)は Authenticated Users:(M) で
一見問題なし → `Get-SmbShare` + `Get-SmbShareAccess` で共有「本」だけ Everyone:Read と判明
(兄弟共有の D/動画は Everyone:Full)。

**直し方**(管理者権限PowerShell必須、通常セッションはAccess Denied):
```powershell
Grant-SmbShareAccess -Name "<共有名>" -AccountName "Everyone" -AccessRight Full -Force
```
またはGUI: 対象フォルダ右クリック→プロパティ→**共有**タブ(セキュリティタブではない)→
「共有(詳細設定)」→「アクセス許可」ボタン→該当アカウントの「フルコントロール」に✓。

**Why**: NTFS権限([[m5ultra_file_server_setup]]の幽霊SID/Authenticated Users欠け問題)とは
**別の場所**にもう一段の許可設定があることを見落としやすい。「見えるのに書けない」は
まずこの2箇所(NTFS=セキュリティタブ / 共有=共有タブ)を両方チェックする。

**How to apply**: 今後同様の「見えるが書き込み不可」報告が来たら、まず
`Get-SmbShareAccess -Name <共有名>` で共有レベルの許可を確認してから、NTFS側(icacls)を疑う順で進める。
