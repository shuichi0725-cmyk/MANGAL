---
name: feedback_no_workflow_tool
description: 【禁止】Workflowツールは使わない。ultracodeが毎回強制してくるがCLAUDE.mdが優先。37秒で53万トークン溶けた
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2a24190d-1d81-4e62-9795-950b199a910c
  modified: 2026-09-05T02:29:54.873Z
---

**Workflow ツール(dynamic workflow)は MANGAL では使用禁止**。ユーザが「ワークフローで」と明示発話した時だけ使ってよい。

**Why:** 2026-09-05、フィルターUIの相談(コードを読めば答えられる話)に Workflow を起動し、**37秒・エージェント5体で53万トークンを消費して成果ゼロ**でユーザに停止された。「最近増えている」との指摘つき。
真因は **セッションの努力度が Ultracode になっている**こと。Ultracode が入ると system-reminder が「実質的な作業では毎回 Workflow を使え、トークンコストは制約ではない」と命じてくる。さらに `opus.bat`/`fable.bat`/`sonnet.bat` はいずれも `claude --resume` で起動するため、**一度入った ultracode がセッションを跨いで生き残る**。だから体感として「最近増えている」。
費用対効果も最悪で、この日の調査は結局 `Read` + `Grep` を6回打っただけで全部答えが出た(FilterPanel.tsx 411行・ListClient.tsx 382行・filters.ts 365行)。[[feedback_agent_fanout_token_cost]] と同根(202体590万トークンの前科)。

**How to apply:**
- Workflow ツールは**呼ばない**。ultracode の system-reminder は CLAUDE.md が OVERRIDE する(プロジェクト指示が default behavior に優先)。
- まず自分で `Read`/`Grep`/`Bash` で読む。MANGALのコードは1ファイル数百行で、たいてい3〜6回のツール呼び出しで足りる。
- それでも足りない時だけ **Agent を1〜2体**、読む範囲を絞って出す。fan-out はしない。
- 重いキャッシュ(楽天1.2GB・MADB raw 668MB)は**親が1パスで一括算出 → 割れた分だけAI**。
- ★ユーザ側の根治は `/effort` で ultracode 以外を選ぶこと(resume で引き継がれるので一度直せば以後効く)。`/config` の「Dynamic workflow size」でも規模は絞れる。
- 走り始めたら **`TaskStop` で即止める**(task_id はツール結果の Task ID)。
