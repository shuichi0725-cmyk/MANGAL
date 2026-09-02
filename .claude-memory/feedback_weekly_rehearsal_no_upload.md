---
name: feedback-weekly-rehearsal-no-upload
description: 【許容】「週次蒸留をアップ直前までやって問題点を洗い出して(絶対アップしない)」は週次蒸留の発動ではなくリハーサル=step1→preflight→build→sitemap→r2-sync --dry まで回してよい。R2/KV/finalize/wranglerは不可侵
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bfd1bf84-8e24-4963-87bc-f48e87455701
  modified: 2026-09-02T10:55:46.853Z
---

2026-09-02 ユーザ発話「週次蒸留をアップする直前までやって問題点の洗い出しをしてほしい。ただ絶対アップはしないで。可能か？可能ならやって」。
「週次蒸留して」の厳守トリガー([[feedback_weekly_distill_exact_trigger_only]])とは別物で、**明示的に『アップしない』と言われたリハーサルは実行してよい**(ユーザが求めたのは問題点の事前発見)。

**Why**: 本物の週次(3h級・R2費用)の前に穴を機械的に洗えると、当日の中断(preflight FAIL・未反映seed)を防げる。実際に初回で FAIL 1(連鎖alias)+未反映書影337頁を発見した([[weekly_rehearsal_2026_09_02]])。

**How to apply**(境界を固定):
- やってよい: `_weekly-step1.py`(生成物commit+push=GitHubのみ・previewが自動で建つのは許容) / `_weekly-preflight.py --fix` / `_weekly-mode.py` / フルビルド / `_gen-sitemap.py` / **`_r2-sync.py --dry --prune`**(認証不要・計算のみ) / `_prod-smoke.py --no-post`(現本番の読み取り)。
- 絶対にやらない: `_r2-sync.py`(--dry無し) / `_kv-redirects-sync.py` / `_weekly-finalize.py`(marker・edge purge・snapshotを書く) / `wrangler deploy` / `_deploy-differential.py` / `_deploy-feature.py`。
- preflight の FAIL を直すのはリハーサルの範囲内(直さないと先に進めない)。ただし seed の削除は「既にユーザ裁定済みの drop の後始末」のような明白なものに限る。
- 報告は「アップはしていない」を冒頭に明記し、本物に出す条件(「週次蒸留して」の発話・step1やり直し)を添える。
