---
name: d_drive_nightly_wake
description: D:(USB 24TB HDD・5分で停止)が勝手に起きる原因の調べ方と結果(2026-11-07)。毎晩22:46ごろ=Windowsの毎日の更新確認の時刻(10/16 22:25起動が基点)。管理者なしで NTFS の記録から追える
metadata:
  node_type: memory
  type: project
  originSessionId: 6c0dac9e-5ae1-45b8-8ced-c362aa0d8de2
  modified: 2026-11-07T14:11:40.716Z
---

ユーザ(2026-11-07):「hddスリープしてると無音なのだがさめると音で分かる。アクセスしてないときはさめないでほしい」。

**調べ方(管理者権限なしで読める)**: `Microsoft-Windows-Ntfs/Operational` の
- id 156 = D: の VCB 独占(1時間ごとのまとめ)。 hold が約9秒 = 寝ていたHDDの回り始めを待った時間 = その1時間に誰かが起こした。
- id 170 = 操作の種類ごとの回数・最大待ち(Open volume for DASD / Read / Create…)。 最大5秒以上 = その操作で起こした。
SMB の接続相手(Get-SmbSession)・タスクスケジューラの記録・Defender の除外は管理者でないと見えない。 445番の確立済み接続(Get-NetTCPConnection)は見える。

**分かったこと(10/30〜11/07)**:
- 毎日1回、 22:45:33〜22:46:32 の間に何かが D: のボリュームを直接開いて起こす(hold 約9秒。 既に起きていた日は 3ms)。 同じ1分に毎日 ソフトウェア保護(SPP #16394)と Windows Update(Defender 定義の入れ直し)が動く = PC 起動(10/16 22:25)を基点にした毎日の更新確認。 **どのプロセスかは未特定**(管理者で wpr/Procmon を 22:44〜22:48 に回せば分かる)。 再起動すると時刻がずれる。
- 違ったもの: ノートン(毎時30分の状態報告で夜だけではない)・23:07 の復元ポイント(PITRTask。 11/5 は作成したのに D: は起きていない)・Windows Search(D: は対象外)・Defender(D: を検査しない)。
- ほかの目覚め: 毎週土曜 2:26 の「ドライブの最適化」(約2分)/私の週1バックアップ(日曜4:00)/私の作業(11/07 14:01〜14:18 Wikipedia ダンプの移動、 17:31〜17:58 バックアップ1回目)。
- 電源設定「ハードディスクの電源を切る」= AC 5分。

関連: [[feedback_no_d_drive]] [[d_drive_external_flaky]] [[self_backup_weekly]]
