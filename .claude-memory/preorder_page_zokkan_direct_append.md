---
name: preorder-page-zokkan-direct-append
description: preorder-pages由来の頁への巻追加は種4不可(種2にseries_key無し)=seed yml直接追記が正
metadata: 
  node_type: memory
  type: project
  originSessionId: 59d8d8ff-b25f-483a-a575-3e5765b36905
  modified: 2026-08-31T06:21:41.230Z
---

予約ドラフト出身の頁(`data/seeds/preorder-pages/*.yml`)は**種2 sqliteに存在しない**ため、
続巻を種4(volumes-supplement)で足そうとしても series_keys の逆引きが空になり効かない。

**How to apply:** 続巻/欠け巻は preorder-pages の当該yml の volumes に**直接追記**(isbn13/release_date/cover_url=実URL/volume_label)→ `_reflect-targeted.py --only <slug>`。
実例= 第17王子の命題(2026-08-31: NDL新着で下巻回収→上下同日刊なので status: completed + year_ended も同時に更新)。
月次蒸留でMADBが追いつき種2に入った後は通常の種4/canonical運用に戻る。[[intake_manifest_ledger_live]]
