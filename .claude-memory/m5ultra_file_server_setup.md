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
