---
name: voldesc_next_slice_todo
description: 巻説明つくって=/clear後に次スライスから再開する保留タスク
metadata: 
  node_type: memory
  type: project
  originSessionId: 97904f9e-0992-4de3-b3a2-7738e71b169c
  modified: 2026-07-22T03:28:33.964Z
---

★保留タスク(2026-07-22 ユーザ指示「クリアーしてから開始したい」): ユーザが `/clear` 後に「巻説明つくって」を再開したら、**次のスライスに進める**。

**背景**: 「1…」帯は非物語で生成0。次の「A…」帯(2026-07-22処理)=104巻caption有のうち物語材料は12巻のみ(穴殺人v3-8/明けても暮れても v2/悪役令嬢/ALIVE v4/ALL OUT柔道 v2/雨の日はお化け v1/アカギv27/悪役令嬢v1)を生成・commit済(seed累計11,703)。残92巻は非物語(TL宣伝/限定版BOX/画集/話数題羅列/新装版の共通premise重複)でskip。この区画(TL・4コマ・アイドル・BL・成人)はcaption薄が続く。

**やること**:
1. `python scripts/_voldesc-material.py --local-only` を再実行(auto=seed未生成のみファイル名順・端から [[feedback_no_popularity_priority]])。前スライスの11巻はseed未書込のため再選定される可能性あり=スキップして先へ。
2. 材料の濃い区画まで進めて、物語材料のある巻だけ生成(150〜400字・水増し禁止・捏造禁止 [[feedback_accuracy_is_the_goal]])。
3. skill volume-desc の手順(Step1材料→Step2生成→Step3 `_voldesc-apply` + commit/push)を踏襲。
4. Opus 4.8 運転前提。

完了・不要になったらこの記憶を削除。
