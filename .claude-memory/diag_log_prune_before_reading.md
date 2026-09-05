---
name: diag_log_prune_before_reading
description: 追記専用の診断簿は掃除してから読む。3本で676行→38行(94%が残骸)。書き手にdedup追加済・日次に組込済
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 74b7cb9b-8792-4d9b-a5f5-6e0efb70e9e8
  modified: 2026-09-05T02:15:41.222Z
---

`docs/production-diagnostics/` の**追記専用の簿**は、掃除しないと膨らんで
「簿に出ているのに誰も読まない」状態になる。skill daily-distill 自身が警告している形骸化そのもの。

**実測(2026-09-05)**: 3本を機械で分解したら **676行のうち94%が残骸**だった。

| 簿 | before → after | 残骸の内訳 |
|---|---|---|
| kana-mismatch | 159 → 2 | 重複5 / 本番にもう無いslug 75 / 解決済・既知の偽陽性 77 |
| slug-gate-pending | 346 → 19 | 重複143 / 本番にもう無いslug 182 / 今のゲートでは一致 2 |
| slug-katakana-pending | 171 → 17 | 本番にもう無いslug 154 |

**How to apply**:
- 読む前に `python scripts/_prune-slug-diag-logs.py --apply`(日次のチェックリストに組込済)。
  消すのは「もう存在しない・既知の偽陽性・解決済み」だけで、実修正が要る行は残る。
- 書き手には**追記dedup**を入れた(`slug_kana_gate` / kana-mismatch。`kata_pending_log` は元からあった)。
  重複143行はこれが無かったせい。**新しく簿を書く時は必ず追記dedupを付ける**。
- ★理想は「毎回作り直す監査型」(`_audit-*.py` のように全走査して簿を再生成する形)。
  追記型は必ず腐るので、新設する簿は監査型に寄せる。

**Why**: 簿は人が消化して初めて意味を持つ。残骸9割の簿は開いた瞬間に諦められる=
検出器を作った意味が消える([[daily_distill_hold_not_requeued]] と同じ失敗の形)。

★**やってはいけない一般化**: 「本番に無いslug率」で簿の腐り具合を一括判定するな。
多くの簿は**設計上「本番に無いもの」を扱う**(shu2-unrendered / seed1-lost / orphan系)し、
slug列が**公開slugでなくSRC stem**の簿もある(no_cover / ongoing-recheck)= [[pubslug_src_stem_generator_trap]]。
2026-09-05 に実際この測り方で「他の簿も100%腐っている」と誤読しかけた。簿ごとに定義を読んでから測る。

関連: [[feedback_sanity_check_tool_warnings]] / [[slug_override_deadform_flat]]
