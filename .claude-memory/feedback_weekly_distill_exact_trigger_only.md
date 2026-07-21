---
name: feedback-weekly-distill-exact-trigger-only
description: 【厳守】週次蒸留は「週次蒸留して」以外のトリガーで絶対発動しない(2026-07-21ユーザ厳命)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-21T10:08:35.626Z
---

週次蒸留(本番フルビルド+R2アップ)は**「週次蒸留して」という発話のみ**で発動する。

**Why:** 2026-07-21、「本番化して」(=productionize-drafts のトリガー)を「本番公開のGO」と拡大解釈し、週次蒸留を代行起動した。ユーザの意図は「本番に載っていない全集関連頁の登録」で、サイト全体のデプロイではなかった。途中で止められ「週次蒸留は絶対『週次蒸留して』以外のトリガーで発動しないで」と厳命。

**How to apply:**
- 「本番化して」「本番に出して」「公開して」等の類語・文脈からの推論では絶対に週次蒸留を始めない。
- 週次蒸留が必要な場面だと判断したら、実行せず「本番サイトへの公開には『週次蒸留して』の発話が必要です」と案内して待つ。
- skill側にも同旨を焼き込み済(.claude/skills/weekly-distill/SKILL.md のトリガー節+NEVER)。
- 関連: [[feedback-production-deploy-gate]](テスト確認→GO→本番) — GOの解釈もこのルールが優先。
