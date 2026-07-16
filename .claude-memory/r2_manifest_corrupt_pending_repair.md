---
name: r2-manifest-corrupt-pending-repair
description: .cache/r2-manifest.json が破損中(7/11同期直後にバイナリ化)。次の週次蒸留がETag照合で自動復元する。それまで「差分反映して」がabortするのは正常=故障と誤認しない
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

**現状(2026-07-17時点・未復元)**: `.cache/r2-manifest.json`(= R2キー→sha256 = 「前回同期した時点で本番R2に何が在るか」の記録)が**中身だけバイナリ化して破損**。バックアップは無い。

- サイズもmtimeも **7/11 20:36:38 のまま**(= R2側の最終更新 20:36:37 の1秒後 = 最後に成功した本番同期の書込時刻)。**書いた直後にmtimeを変えず中身だけ壊れた** = ディスク層の破損。[[d-drive-external-flaky]] の外付けが疑わしいが未確定。
- 他の `.cache` 資産(db-v2.sqlite / isbn-page-index / rakuten-isbn / covers)は**全て健全**。壊れたのはこの1本だけ。[[pc-migration-2026-07-17]] のコピー事故ではない(C:とD:で同一バイト = 壊れた物を忠実に運んだ)。

**復旧は自動**(= commit 60cabf3ba で実装済み。実行はまだ):
- 次に **「週次蒸留して」** と言えば `_r2-sync.py` が 破損manifestを `r2-manifest-bad-<ts>.json` へ退避 → **R2のETag(単一part=MD5)とローカルMD5を照合して欠損キーを補完** → **134,066件は再アップせず manifest だけ復元**される。追加コストはバケット一覧1回(~30秒)。
- ★**それまで「差分反映して」は abort する = 意図した fail-closed**。manifestは `_deploy-differential.py` で「その頁が本番で稼働中か」(`was_live`)の判定源であり、空のまま進むと**稼働中の頁を「元々未掲載のschema不良」と誤判定して黙って除外 = 本番劣化**するため。**原因不明の故障と誤認して回避策を打たないこと**。

**復元を確認したらこの記憶は消す**(= 一時状態の記録)。恒久の仕組み側は [[hosting_worker_r2_architecture]] とコード内コメントが正。
