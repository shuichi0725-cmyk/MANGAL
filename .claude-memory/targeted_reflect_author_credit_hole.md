---
name: targeted_reflect_author_credit_hole
description: 【型・是正済】targeted反映(--only)だと著者が「本のクレジット」でなくNDL典拠の代表名に化ける。遅延ロードの順序穴。2026-09-10修正
metadata: 
  node_type: memory
  type: project
  originSessionId: 58a222b6-cb74-4572-9905-4dacb5f8ddb9
  modified: 2026-09-10T04:24:40.504Z
---

2026-09-10 実踏。per-case で1頁だけ再生成したら、著者が **百地元 → みやこかっく** に silent に化けた。

## 機構
`_promote-bulk-v2.py` は「表示名はその本のクレジット」(ユーザ方針 2026-07-26)を
`_apply_book_credit()` で実現している。参照する `_ISBN2CREDIT`(ISBN→MADB schema:creator)は
`_load_pub_resolver()` の**遅延ロード**で埋まるが、その初回呼び出しは `build_yml` 内の
`edition_pub_name()` = **`_apply_book_credit` より後**だった。

帰結:
- **フルpromote(66k)= 1頁目だけ効かない**(埋もれて誰も気づかない)
- **`--only`(targeted反映)= 唯一の頁が必ず化ける**

化ける先は `mangaka.name` = NDL典拠の代表名。同一人物の別名義が `alt_names` に束ねられているため、
本のクレジット名を持っていても表示は代表名になる(例: ndl:00131073 = みやこかっく|七野りく|百地元)。

## 是正
`_apply_book_credit` 冒頭で `_load_pub_resolver()` を明示呼び出し(冪等)。commit efb2a3b1e。

## ★掃引結果 = 36頁(自動適用は禁止)
`scripts/_audit-book-credit-drift.py`(本件を機に新設)で本番66kを1パス掃引。
出力 `docs/production-diagnostics/book-credit-drift.tsv`。**2型が混在するので一括適用しない**:
- **型A 改名・旧字**: 桑田二郎↔次郎10 / 竹宮惠子↔恵子2 / 石ノ森↔石森1 / ダイナミックプロ2 / 秋★枝↔秋枝 …
  → 方針上は「その本のクレジット」が正だが、**作家の統一表記としては現状が正**のことがある = ユーザ裁定
- **型B 別名義**: 青インク→ソウマトウ(シャドーハウス) / ハイソンヤギ→モリコロス(猫と紳士のティールーム
  = [[gate_mismatch_reveals_our_own_error]] に既出の宿題) / 樹林伸→龍門諒 / 泉すずしろ→北国良人 …
  → 明白な誤りと、**mangaka の過統合**(原作者と作画者が同一人物として束ねられている)疑いが混在

月次サニティへの登録は未実施(裁定待ち。CLAUDE.md の表と docs は触っていないので3点突合ゲートは 0 のまま)。

**Why:** per-case反映のたびに、直した頁だけ著者が別名義へ化けていた。番人が無く silent。
**How to apply:** 遅延ロードに依存する是正層は「1頁だけ生成」で必ず検算する。
per-case後は頁 dump を旧版と diff して、**直したフィールド以外が動いていないか**を見る。
関連: [[reflect_protocol_fast]] [[author_data_map]] [[feedback_one_bug_means_a_class]]
[[madb_parallel_title_inversion]] [[seed_silently_ineffective_class]]
