---
name: volgap_virtual_false_positives
description: 【封鎖済】巻抜け仮想(_volgap-virtual.py)の偽陽性2種=editions無しoverrideで巻を全消し/canonical結線頁に種4を仮想適用。数字の読み方も変わる
metadata: 
  node_type: memory
  type: project
  originSessionId: 732ebafe-0cf0-4d76-96d4-8692ce4b06b2
  modified: 2026-09-02T16:26:12.942Z
---

**2026-09-03 に `scripts/_volgap-virtual.py` を修正**。それ以前の残gap件数は下記2種の偽陽性を含んでいる。

## 封鎖した偽陽性
1. **editions を持たない edition-overrides entry を「空の版」と解釈して頁の巻を全消し**していた。overrides 739件中 **287件が title/kana/year だけの entry**(頁分割・年是正用)で、監査対象1417作のうち17件が該当 → 在りもしない穴が出ていた
2. **edition-canonical 結線頁に種4/merge partner を仮想適用**していた。canonical は standard を丸ごと置換し suppress_types で他版も消すので、**種4の巻は頁に出られない**(`open_tail: true` の頁だけは例外なので従来どおり仮想適用)

## 数字の読み方
- 修正後(2026-09-03): 対象1417作 / **適用前128 → 適用後136(closed 8)**
- 偽陽性 −3(new-normal / macross-7-trash / うら刑事の一部)、canonical頁の**実gap +3**(赤白たまご/プラモ狂四郎/ワイルド7)
- ★**適用後 > 適用前** は正常。seedを当てると穴が開く頁が16件あり、正体は**種4-auto/merge partnerの巨大巻番号**(doraemon=種4-auto n=286、umanari-1-haron-theater=merge partnerの年→巻番号型)。誤番号seedの signal なので per-case で潰す
- ★canonical結線頁の残gapは **canonicalに巻を足すのが正**(種4を足しても出ない)

[[volgap_virtual_tool_trigger]] [[volgap_diagnosis_order]] [[edition_canonical_mechanism]]
