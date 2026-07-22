---
name: voldesc_next_slice_todo
description: 巻説明つくって=/clear後に次スライスから再開する保留タスク
metadata: 
  node_type: memory
  type: project
  originSessionId: 97904f9e-0992-4de3-b3a2-7738e71b169c
  modified: 2026-07-22T00:33:21.886Z
---

★保留タスク(2026-07-22 ユーザ指示「クリアーしてから開始したい」): ユーザが `/clear` 後に「巻説明つくって」を再開したら、**次のスライスに進める**。

**背景**: 直近スライス(ファイル名順・タイトル頭「1…」帯)は11巻caption有だが全て非物語(話数題羅列/宣伝定型/限定版BOX/プレースホルダ)で生成0。91巻はローカル材料なし→no-material台帳(累計1,426)。この区画はTL/成人/宣伝主体でcaption薄。

**やること**:
1. `python scripts/_voldesc-material.py --local-only` を再実行(auto=seed未生成のみファイル名順・端から [[feedback_no_popularity_priority]])。前スライスの11巻はseed未書込のため再選定される可能性あり=スキップして先へ。
2. 材料の濃い区画まで進めて、物語材料のある巻だけ生成(150〜400字・水増し禁止・捏造禁止 [[feedback_accuracy_is_the_goal]])。
3. skill volume-desc の手順(Step1材料→Step2生成→Step3 `_voldesc-apply` + commit/push)を踏襲。
4. Opus 4.8 運転前提。

完了・不要になったらこの記憶を削除。
