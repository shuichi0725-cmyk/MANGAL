---
name: enrich-7k-resume-state
description: 【進行中】キャッチ/詳細7,048作の一括エンリッチ(分散WF)の再開手順と進捗。「エンリッチ続き」で再開
metadata:
  type: project
---

キャッチ/詳細の分散エンリッチ(2026-07-07開始)。対象7,048作=71バッチ(100作/バッチ)。

- 材料: `.cache/enrich-batches/batch-000..070.json` (楽天caption。再生成は `.cache/_prep_enrich_batches.py`)
- 完了出力: `.cache/enrich-out/batch-NNN.json` — **ファイルが在るバッチ=完了済み(再生成不要)**
- 再開: 出力ファイルの無いバッチ番号だけ Workflow並列で回す(プロンプトはworkflowsスクリプト保存済み
  `enrich-catch-synopsis-7k-sonnet-wf_8145bc6c-0a8.js` を流用、DONEリストを実ファイルから更新)
- モデル: sonnet(4.6→アップデート後は解決先を確認、Sonnet 5になっていればそのまま得)。
  batch000-008=Fable5製(品質基準)。Sonnet製と比較検収する。
- 完了後: 機械検収(文字数20-40/60-120・master32外genre拒否・catch≠synopsis先頭一致)
  → catch-ja.json+synopsis-slug-ja.json純粋追加 → manga.v2パッチ(genres_add+provisional)
  → 本番索引再生成 → 「反映して」相当。適用は前回93作の適用スクリプト方式([[enrich-catch-synopsis]] skill Step4)。
