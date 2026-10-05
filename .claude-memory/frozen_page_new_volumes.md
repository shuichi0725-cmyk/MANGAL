---
name: frozen_page_new_volumes
description: 【型・検出器#35】手で巻を固定した頁(edition-overrides/canonical)は新刊が永久に出ない(SHIORI EXPERIENCE型)。楽天liveで照会=月次heavy組込済
metadata:
  type: project
---

2026-10-05 発見: SHIORI EXPERIENCE は 8/7 の頁統合で edition-overrides が22巻固定 → 23〜26巻(新刊・978-4-301)が未掲載。
当時の注記「9784301007227=後年付番」は誤り(=26巻)。 #27第2部は種2の続巻しか見ず、MADBが追いつく前の新刊=本命を拾えない。

- 検出器 `scripts/_audit-frozen-page-new-volumes.py`(楽天live「題+次の巻番号」・題は巻番号を除いて完全一致・著者一致・ISBN未在)。
  月次サニティ #35(heavy=`run sanity --heavy`)に3点登録済(CLAUDE.md索引/docs本文/DETECTORS)。 約25分/1,200頁。
- 初回: 1,191頁 → 本物5作(サンダー3 10・ゴルゴ13 222・釣りバカ119・金瓶梅64・少年ケニヤ角川文庫19-20)= 追加済(3775a384e)。
- 入れ口: overrides頁=edition-overridesの巻の並び / canonical頁=canonical本体。 ★文字として差し込む(JSON/YAMLを丸ごと
  書き直すと書式が変わり差分数万行=実踏)。 書影は実物だけ cover-override(発売前 .gif は入れない=差し替えを止める)。
- 残(2026-10-05 調査済・未適用): 昭和極道史34(9784821192434・1988-09・楽天のみ=NDL/MADB無し・ISBN連番は整合)/
  サーキットの狼 JC は全27巻=23〜27欠け(NDLで確認・ISBN 23=9784088524733/26=…764/27=…771、24/25はISBN無し)/
  エスパー魔美 = 頁のてんとう虫版がISBNはてんとう虫・日付はマンガくん/少年ビッグ版の取り違え(奇子型)= per-case で版を組み直す。
関連 [[edition_canonical_mechanism]] [[edition_overrides_key_is_public_slug]] [[ebook_only_volumes_mechanism]]
