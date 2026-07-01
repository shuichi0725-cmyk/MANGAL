---
name: harvest_match_mechanism_applied
description: 題+巻番号→楽天item照合の共通機構(完成・適用済)。発売日逆行/巻抜けA是正の実装と版整合の知見
metadata: 
  node_type: memory
  type: project
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

「題+巻番号→楽天item照合」の共通機構を実装・A是正適用済(2026-06-27)。[[harvest_based_fix_mechanism]]の実行結果。

## 共通機構 = `scripts/_rakuten_match_lib.py`
- `norm()` NFKC+記号/空白除去, `parse_vol()` 末尾巻トークン剥がし(★ゴルゴ13型=題内末尾数字を巻番号と誤読しない。空白/括弧境界必須), `parse_salesdate()` 和文→(Y,M,D), `parse_prod_date()`, `recs_for/pub_key/primary_publisher/inversions`。
- ★**安全規則=残差題完全一致**: 巻トークン剥がした残差題が target題(norm)と完全一致の時だけ採用 → スピンオフ/外伝/データファイル/超全集を自然除外。
- index: `_build-rakuten-focus-index.py` が対象slugのみ focused index(.cache/rakuten-focus-index.pkl)。818k item 1パス。harvest生= `.cache/rakuten-isbn-delta.jsonl`(828MB)+`rakuten-isbn.jsonl`。★utf-8固定open必須(Win console=cp932で化け)。

## ① 発売日逆行 (`_apply-date-disorder.py`) = 適用済
- 逆行 851→547(203slug/2846巻)。durable= **`data/seeds/release-date-override.jsonl`**(ISBN13→初版日 強制override)+ promote `get_release_date_override()`/`_eff_date`で種2値より優先(補完supplementは種2空時のみ=別物)。
- ★**版整合**: 全版横断の最古はNG(版混在で逆行増)。**主版=最多巻カバーpublisher(ISBN先頭7桁)内の最古printing**のみ採用。net-improving slug+ISBN-key+per-slug安全ゲート。
- ★**Frankenstein版混在**(wild-7=1〜18巻1986再版+19〜48巻1974初版を1ページ混載 / 無用ノ介 / おれは鉄兵)は日付だけで直せない構造問題=regressor14として除外→[[multi_edition_unification_pending]]。

## ② 巻抜け (`_apply-volume-gaps.py`) = 適用済
- 247巻を種4(volumes-supplement.yml 528→775)へ純粋追加(textual append・既存無改変)。
- ★**紐付け=既存巻ISBN→db-v2(volumes→editions→series)逆引きでseries_key確定**(題でなくISBN実体。同名異作封鎖)。db= `.cache/db-v2.sqlite`(promote/registerが使う実体。db.sqliteは空)。
- gate: db既存番号/候補ISBN重複/前後present巻と日付矛盾66 をskip。例=黄昏流星群72-74・剣客商売50。

## 共通の注意
- ★本番反映は**次回promote**(override seed/種4をpromoteが読む)。seed commitだけでは本番yml不変。manga.v2は**gitignore**(68k生成物・1ファイルのみtracked)。
- 慎重原則=dry-run/可逆(.cache backup+changelog)/小バッチ/種2不変を遵守([[feedback_dont_repeat_regrouping_error]])。
- 残: 日付regressor14+date_conflict66+ISBN-None301は版分離タスク。次=B(NDL典拠ID同名異人分離)。
