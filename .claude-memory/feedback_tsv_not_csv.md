---
name: feedback_tsv_not_csv
description: データ書き出しはCSVでなくTSVで(ユーザ明示・2026-06-18)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ec751580-3d99-475b-940c-cf0e3f1feada
---

ユーザへのデータ一覧の書き出しは **CSVでなくTSV** で出す(2026-06-18 明示指示「今後csvじゃなくtsvで」)。

**Why:** ユーザの取り回し都合(タブ区切りの方が扱いやすい)。
**How to apply:** 一覧・台帳・ダンプは `.tsv`(タブ区切り)。Excel用にUTF-8 BOMは付けてよい。既存のCSV生成も今後はTSVに寄せる。
