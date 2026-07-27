---
name: m5ultra-file-server-setup
description: "このPC(M5_Ultra)=家庭内ファイルサーバー構成(2026-07-17構築): 固定IP192.168.0.146・E:共有・share1ローカルアカウント認証・スリープ無効。共有トラブル時の勘所つき"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

このPC = **M5_Ultra**、家庭内ファイルサーバー兼リモート作業機(2026-07-17セットアップ)。

- **固定IP 192.168.0.146**(イーサネット3・DHCP無効)。ネットワーク=プライベート・探索サービス4本(fdPHost/FDResPub/SSDPSRV/upnphost)自動起動。
- **共有 = E:\ 全体**(`\\M5_Ultra\E`)。E:は旧PC由来のドライブで、**旧PCの幽霊SID権限**が居た(本/動画フォルダ拒否事件)→ `takeown /F E:\ /R` + `icacls E:\ /reset /T /C` で全リセット済み。新たに拒否フォルダが出たら同じ2行。
- **認証 = ローカルアカウント `share1`**(共有専用・パスワードはユーザーのみ知る)。★Microsoftアカウント名/PINはSMB認証に使えない罠を回避するための設計。クライアントは Android(アプリ内保存)+Win11 Home(cmdkeyで`M5_Ultra`と`192.168.0.146`の両ターゲット保存済み)。
- ★Win11 Home側の教訓: **`net use /user:`付き永続マッピングは資格情報保存庫とケンカして毎回パスワードを聞く**→ `/user:無し`の`net use Z: \\192.168.0.146\E /persistent:yes`(認証は保存庫任せ)で解決。
- **スリープ/休止=無効化済み**(powercfg standby-timeout-ac 0)= ファイルサーバー+アイドル運転+リモート操作の常時稼働前提。ロック画面問題の主因もこれで解消。
- share1はログイン画面に出る(隠すなら Winlogon\SpecialAccounts\UserList に share1=0、未実施)。


## 2026-07-27 追記(D:共有トラブルの解決記録)
- ★このClaude稼働PC自体が M5_Ultra(hostname確認済・192.168.0.146)。共有=D/D$/E/動画/本(+管理共有)。
- 「D:\本」だけ共有拒否 = 幽霊SIDでなく**Authenticated Users欠け**(所有者個人+Admin+SYSTEMのみの非継承ACL)。修復= takeown /R + icacls /reset /T で継承復活(データ無傷・実施済)。
- ★接続の合言葉=「共有は share1」: Microsoftアカウントのメール(shuichi0725@gmail.com)はSMBに使えない(ローカルアカウント認証)。空白入り「chiba shuichi」もAndroidアプリで事故る。
- Explorerは**検索ボックスでなくアドレスバー**に \192.168.0.146(検索ボックスだと「一致する項目はありません」)。
- 日本語共有名「本」はAndroidアプリが弾く場合あり→ その時は D 共有経由 or 英字エイリアス(New-SmbShare -Name books -Path D:\本 -ReadAccess Everyone)。
