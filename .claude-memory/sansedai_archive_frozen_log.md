---
name: sansedai-archive-frozen-log
description: 今日の一冊 過去ログ=凍結ログ方式(2026-07-30ユーザ裁定「一度表示した日は永久固定。変わったら過去ログではない」)
metadata: 
  node_type: memory
  type: project
  originSessionId: d1040cbb-d0d0-4f0c-89c0-0c78d44dc085
  modified: 2026-07-29T15:39:12.157Z
---

「三世代/今日の一冊」の過去ログ(/sansedai-archive)は **凍結ログが正**。式再現(dayIndex % pool)はstock改版で過去日が遡って化ける事故を起こした(2026-07月中、stock 741→737→735の3改版)。

- 実体: `public/data/sansedai-log.json` = {日付: picks3人分}。開始日=**2026-06-01固定**、月単位セクション表示(当月のみ展開)。
- 生成: `scripts/_gen-sansedai-log.py` = **昨日まで**を純粋追記(既存日は絶対不変・今日は表示進行中なので凍結しない)。
- ★順序が命: `_gen-corner-stocks.py` が **stock上書きの前に** 凍結を自動実行(旧stockで表示された日を旧stockのまま固定)。この順序を崩さない。
- 未凍結日(直近ビルド後)はArchiveClientが式でfallback→次回実行で固定。

**Why:** 過去ログの本質は「実際に表示された記録」。再計算で変わるならログではない(ユーザ裁定)。
**How to apply:** 今後アーカイブ性のあるコーナーを作る時も同方式(表示済み=凍結・純粋追記・生成順序ガード)を踏襲する。[[sansedai_featured_stock_state]]
