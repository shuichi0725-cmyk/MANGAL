---
name: feedback_idle_month_rehearsal
description: 【方針】蒸留の空振り月(新releaseなし)は手順の検算(--rehearsal)と罠の機械封鎖に使う。手順は Opus が回す前提で「script に畳む・Go引用必須・散文の自己申告禁止」まで落とす
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f2cce216-3e15-4659-8ab0-350d4f267a00
  modified: 2026-09-02T14:07:22.804Z
---

2026-09-02 ユーザ指示: 「今月次蒸留を行っても前回と何も変わらない。ただ手順や Opus が回す時に少しでもスムーズに回る・事故を防ぐために見直してほしい」。

**Why**: 月次蒸留は月1回しか本番機会が無く、弱いモデルが手打ちの env override 列を再現すると事故る(1.2.19 実害: clean の置き場違いで出版社(unknown)1,182頁 / 種4-auto 全消し 883巻)。新 release が無い月は「何も回さない」が正解だが、その時間は **取込済 tag でのリハーサル(`phase1 --rehearsal`=純増0が期待値)と罠の機械封鎖**に使えば、次の本番が安全になる。

**How to apply**:
- `status` が「新releaseなし」なら実蒸留は回さない(回しても種2不変・数時間の無駄)。代わりに手順の検算・封鎖を提案する。
- 手順の磨き方の優先順: ①手打ちコマンド列は script に畳む(env/パス/tag を人が打たない) ②破壊的操作は「ユーザ発話の引用」を引数に要求する(`--go`) ③成功判定は script の exit 0+数値引用(散文の自己申告を認めない) ④長時間ジョブはデタッチ起動(Bash timeout で殺されない) ⑤検出器は runner で一括+前回比Δ。
- 検算は本物のデータで(取込済 tag の再計算=期待値0、旧 raw との差分=記録値と突合)。所要も実測して skill に書く。
- 関連: [[monthly_distill_orchestrator]] [[feedback_memory_vs_skill_policy]] [[feedback_efficiency_first]] [[seed4_auto_wipe_accident]]
