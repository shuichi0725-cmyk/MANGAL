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
- 要確認3作 = 全部適用済(2026-10-05): サーキットの狼 JC 27巻(cbaaefd5d)/ エスパー魔美 = 原版を通常版に組み直し(a78b6a941)/
  昭和極道史 34巻 = ユーザ提示のNDL TSV+Wikipedia で確定して追加(d5a3130b0)。 詳細は [[old_work_reprint_date_class]]。
関連 [[edition_canonical_mechanism]] [[edition_overrides_key_is_public_slug]] [[ebook_only_volumes_mechanism]]

## 2026-10-08 日次蒸留に組み込み(手作業→道具)
- 予約の続巻が固定頁に来た時は `_preorder-apply-zokkan.py` が **override の巻の並びへ直接追記**する(通常版1つ・巻連続・出版社一致・
  発売日順のゲート)。初回=9/14〜10/3 に種4へ入ったまま出ていなかった6冊(無敗のふたり6・Kiss me crying 6・聖女に嘘は通じない7 等)。
- canonical 頁は override より後に editions を組み直す= override 併用 or open_tail 無しなら保留簿へ出し、
  `scripts/_canonical-append-volume.py <stem> <巻> <isbn> <日付> --why …` で本体へ足す(ゴルゴ13 223・チキン49・新しいゲーム始めました5)。
- ★ゴルゴ13: override(通常版1-220/コンパクト177/文庫40)が残っていて open_tail が効かなかった → 2026-10-08 ユーザ裁定
  「外して抜けないように」で override の editions を削除し、文庫版40冊を canonical の extra_editions(+suppress_types: bunkobon)で固定。
  外す前後で頁の版・巻・ISBN・日付は完全一致(試し生成と反映後の両方で検算)。以後の新刊は種4→open_tail で自動。
  ★推測(ユーザ): override は週次/月次で巻が抜ける対策だった = 外すなら同じ守りを canonical 側に移す、が型。
