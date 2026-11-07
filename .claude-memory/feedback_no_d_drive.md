---
name: feedback_no_d_drive
description: "【★厳守】Dドライブは使わない。置き場は C:(リポジトリの .cache = C: 実体)。C: の空きは十分(2026-11-07 で 788GB)。報告でも D: の空き等を持ち出さない"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 6c0dac9e-5ae1-45b8-8ced-c362aa0d8de2
  modified: 2026-11-07T06:29:48.526Z
---

ユーザ(2026-11-07):「前にも何度か述べたがDドライブは使わないでCドライブにはまだまだ余裕があるはず」。

**Why:** D: は外付けで突然認識が外れる([[d_drive_external_flaky]])。 大きいデータ(Wikipedia ダンプ 5GB 等)を置く先として D: を選ぶ/話題に出すこと自体が誤り。
2026-11-07 は実際には C:(.cache)に落としていたのに、 報告で「Dドライブには17TBの空き」と書いてユーザに D: を使ったと思わせた。

**How to apply:**
- 新しい置き場は **リポジトリ `.cache/`(C: 実体)** か C: の下。 `df` で空きを見る時も C: だけを見る・報告する。
- 道具で大きいファイルの置き場を決める時は、 解決後のパスが D: なら止める(`scripts/_wiki_local.py` の `_assert_c_drive` が手本)。
- 既存の D: 依存 = `_deploy-differential.py` の `DIFFDATA = D:\mangal-cache\diffdata` ハードコード([[pc_migration_2026_07_17]])。 移すかはユーザに確認してから。
- 関連: [[d_drive_external_flaky]] [[feedback_user_directive_supremacy]]
