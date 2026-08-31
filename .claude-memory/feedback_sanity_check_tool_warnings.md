---
name: feedback-sanity-check-tool-warnings
description: scriptの警告数値を鵜呑みで報告しない。桁・日付は暗算で検算してから伝える
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd02af38-42f4-4acb-9f59-ae607bc37eeb
  modified: 2026-08-31T14:07:31.552Z
---

script が出した警告・推計をそのままユーザに報告しない。**桁と日付は暗算で検算**してから伝える。

**Why**: 2026-08-31 週次で R2予算警告「期末まで週次あと8回→超過見込み」をそのまま報告し
「来週以降は差分週に」とまで進言したが、ユーザに「どう計算しても超過しないよ?」と指摘された。
27日〆で8-31から残り8週は暦上あり得ない(正=3回)= 30秒の暗算で見抜けた。
原因は `_r2_ops_ledger.py` の期末算出バグ(+35日が月を2つ跨ぐ)で、即修正済み。

**How to apply**: 警告に基づいてユーザへ行動変更を進言する前に、その数値が常識(暦・DB規模・
過去実測)と整合するか一度自分で計算する。合わなければ算出コードを疑って先に読む。
関連: [[feedback_accuracy_is_the_goal]]
