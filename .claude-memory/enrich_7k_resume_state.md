---
name: enrich-7k-resume-state
description: 【中断・保留】キャッチ/詳細7,048作エンリッチ。セッション枠問題で一括WFは破棄(2026-07-07ユーザ裁定)。成果物10バッチはgit保存済み。再開条件と手順
metadata:
  type: project
---

キャッチ/詳細の分散エンリッチ(対象7,048作=71バッチ)は**2026-07-07にユーザ裁定で一時破棄**。
理由: Workflowのサブエージェント(Sonnet 5でも)が**セッション枠を大量消費**し、他の作業がもたない。

- **完了10バッチ(約1,000作)= `data/enrich-out-2026-07/`にgit保存済み**(000-008=Fable5製, 009=Sonnet5製・品質良)。未適用。
- 材料は `.cache/enrich-batches/`(消えたら `.cache/_prep_enrich_batches.py` で再生成可)。
- **再開条件**: セッション枠に余裕がある時に小分け(1日5-10バッチ等)で回す、またはAPI課金側で回す構成を作る。全量一括はしない。
- 再開手順: 出力ファイルの無いバッチ番号だけWF並列(スクリプトはworkflows/scripts/enrich-catch-synopsis-7k-sonnet5-*.js)。
- **適用手順**(バッチが揃い次第 or 部分適用も可): 機械検収(文字数20-40/60-120・master外genre拒否・catch≠synopsis)→catch-ja.json+synopsis-slug-ja.json純粋追加→manga.v2パッチ(genres_add+provisional)→索引再生成→反映。前回93作の適用方式([[enrich-catch-synopsis]] skill Step4)。
- 完了10バッチだけ先に適用するのは有効(1,000作分の価値)——ユーザに確認して実施。
