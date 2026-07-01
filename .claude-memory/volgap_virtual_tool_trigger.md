---
name: volgap_virtual_tool_trigger
description: 【トリガー語】「巻抜け仮想」と言われたら _volgap-virtual.py を走らせ残巻抜けを報告する
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

ユーザが **「巻抜け仮想」**(または「巻抜けチェック」「仮想で確認」)と発話したら、即:
`python scripts/_volgap-virtual.py --list` を実行し、「適用前gap / 適用後gap / closed / 残N」を報告する。

**何**: テスト環境(mangal-preview)の「テスト専用フィルタ→巻抜け✓」を本番DBで仮想再現するツール。未promoteのseed(種4 supplement+auto / series-merge手動+auto / edition-overrides奇子型=版完全置換)を本番manga.v2に仮想適用し、build-list-index同等のvol_gap判定を再計算。promote(~90分)待たず**80秒**で残巻抜けを算出。冪等。

**出力**: `docs/production-diagnostics/vol_gap_virtual_remain.tsv`(slug / title / 版type:欠番)= per-case worklist。

**運用**: per-case修正のたびにこれで再確認する習慣(自分の修正の欠陥も炙る=cyborg-009 vol34抜けを検出した実績)。

**Why**: ユーザは修正後の残を素早く知りたい。本番promoteは重い。
**How to apply**: トリガー語で即実行・即報告。指定なくても節目で自発的に走らせてよい。

関連: [[volgap_per_case_cleanup_state]]
