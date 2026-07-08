---
name: daily_distill_classifier_gate
description: 日次蒸留の分類器は設計台帳(intake-manifest-gate-design)の型1/型4に従う。①zokkanは著者集合+正規化題(特装版/サブ剥がし)でマッチ
metadata:
  node_type: memory
  type: reference
---

日次蒸留A(楽天予約)の分類は**設計台帳 docs/intake-manifest-gate-design.md の型分類が正典**。記録表=docs/production-diagnostics/preorder-triage.tsv。

## 水増しの罠と恒久対処(2026-07-08 ユーザ指摘)
- ★**①zokkan(型1 new_volume=既存クラスタへの新刊)の題照合が完全一致だと、表記揺れ(特装版/【】/〜サブ〜/-〇〇編)で外れ、既存続巻が④ex_midに大量水増し**される(ポケスペ65/バキ外伝17/入間くん特装版50型)。
- 対処: `_preorder-classify.py`に**norm_strip(特装版/【】/サブ/版名を剥がす)+page_by_stripped索引+著者集合overlap必須の②次マッチ**を追加(設計台帳型1準拠)。同題別作は著者ゲートで弾く。
- ★**特装版/限定版/BOX/画集=型4 new_edition=scope外skip**(①続巻に混ぜない)。
- 実績: 892の④のうち230が既存続巻(→①種4回収・反映)、44が特装scope外。真の新作④=約724(大半は単発途中巻で全巻回収不成立=draft不可)。
- ★教訓: 件数を報告する前に「既存/コンビニ/特装を除いたか」を必ず自問(ユーザは水増しに敏感)。コンビニ=レーベル判定・既存=ISBN索引+**著者集合+正規化題**の両輪。
