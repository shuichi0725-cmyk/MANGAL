---
name: feedback_production_deploy_gate
description: 【厳守】本番(R2)へのビルド/同期はユーザの明示トリガー(「週次蒸留して」等)まで実行しない。変更は必ずテスト環境で確認→GO→本番
metadata:
  type: feedback
---

2026-07-03 ユーザ指摘。UI修正(コーナー動的化/検索高速化)を私がテスト確認を経ずに本番向けビルド/同期へ進めた→「まだ変更してほしいところがあったのに」。

**Why**: 本番更新のタイミングはユーザの権限。テスト環境が確認の場である以上、そこを飛ばすと未確認の変更が本番に載る。R2 stagingでも「本番系列」への反映は同じ扱い。

**How to apply**:
- 変更(UI/データとも) → まず**テスト環境(mangal-preview)** → ユーザ確認 → **明示トリガー**(「週次蒸留して」=フルビルド+フル同期 / 「反映して」=差分)を待って本番系列へ。
- 私が本番向けbuild/r2-syncを自発的に始めない。準備(ローカルbuild)まではよいが、**同期はトリガー待ち**。
- 関連: [[feedback_user_directive_supremacy]] [[preview_deploy_pitfalls]]
