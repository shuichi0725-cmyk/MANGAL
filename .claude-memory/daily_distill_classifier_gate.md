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

## ★過去ドラフト再カウントの罠(2026-07-09 ユーザ指摘・的中)
- ★分類器はISBNを**production索引(isbn-page-index)としか照合しない**。**前回セッションでpreviewドラフト化したが本番未promoteの作品**は、次回harvestで**別ISBN(後続巻)がfreshになると新規に再カウント**される(ビューティーポップReturns/デュエマRX/STRAY5等20件が実害)。
- ★「増加分(latest-prev)」だけでは不十分。増加分でも**過去にドラフト済みの作品**が混じる(ISBN基準のfreshは通るが、作品としては前回既知)。
- 対処(今回): `.cache/preorders/drafts*`(過去ドラフト2250件)の**題(base正規化)と突合して除去** → 真に今回のみ30頁。
- ★恒久策: (1)確認済みドラフトを`preorder-pages`にpromote(=durable skip・skill既定フロー) or (2)gen-preview/classifyが過去draft題を除外ゲートに追加。**未promoteドラフトが溜まると毎回再カウントされる**。
- ★教訓: 「増加分」報告の前に「過去ドラフト済みを除いたか」も自問(ISBN freshだけでは前回作が混じる)。ユーザは"前回見た"に敏感で正確。
