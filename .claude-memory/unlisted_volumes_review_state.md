---
name: unlisted_volumes_review_state
description: 【進行中】「頁は在るのに巻だけ出ていない」①の裁定。裁定表は生成器化済(_gen-shu2-unlisted-review.py)・現在69頁。previewは①セット
metadata: 
  node_type: memory
  type: project
  originSessionId: 19c40654-3fa1-4eb7-af6e-40057dab95ee
  modified: 2026-09-06T13:29:11.075Z
---

2026-09-06 開始。 検出器 = [[unlisted_volumes_trinity_type]]。

## ★裁定表は **生成器で作る**(2026-09-06 に手打ち → 生成器化)
```
python scripts/_gen-shu2-unlisted-review.py     # 芯TSVが本番ymlより古ければ検出器から自動で作り直す
```
- 出力 = `docs/production-diagnostics/shu2-unlisted-review.tsv`
  (1行1頁 / **#列 = ヘッダ込みの表示行番号** = 「見なおしの N なおして」の N)。
- ★**旧・手打ち表は凍っていた**: 是正済み3頁(悪役令嬢後宮物語 / エイリアンヘッドバット /
  皆様の玩具です)が残ったままだった = [[volgap_leading_gap_and_frozen_input]] と同じ形。
  生成器は毎回「前回比: 解決N頁 / 新規N頁」を出す。 ★**直したら必ず回し直す。行番号は振り直る**。

## いまの状態(2026-09-06)
- **preview = ①のセット**(無作為3,000頁セットは退場済み)。
- **69頁**。 判定の目安の内訳:
  | 目安 | 頁 | 意味 |
  |---|---|---|
  | 同レーベル=素直な取りこぼし | 22 | imprint 完全一致。 まずここから |
  | 同レーベル(包含(サブレーベル)) | 4 | ヤンマガKC ⊂ ヤンマガKCスペシャル 型 |
  | 同レーベル(ラテン⇔カナで同一) | 2 | Wings comics ⇔ ウィングス・コミックス 型 |
  | ★別レーベル | 25 | 版タブ/別作品/非掲載の判断が先 |
  | ★頁側imprintが空=比較不能 | 13 | ★レーベルで裁けない = 著者・発売日連続性で見る |
  | ★誤番号(900以上) | 2 | 一騎当千1000巻 / こち亀999巻 |
  | ★一部だけ別レーベル=混在 | 1 | |
- ★**「imprintが空」は旧表では「同レーベル=素直な取りこぼし」に入っていた**(空==空 が一致と判定
  されていた)。 **証拠ゼロなのに一番安いバケツ**だったので分離した。 ここは足す前に裏取りが要る。
- 処理済み: 悪役令嬢後宮物語～王国激動編～ 6,7巻(series-merge 3sid統合) /
  エイリアンヘッドバット 2巻(preorder-pages 直接追記) / 皆様の玩具です 1-3巻。

## 足し方の分岐
1. 通常頁 = **種4**(imprint を頁の既存版に合わせる。 合わせないと幻の版ができる
   → [[edition_run_split_arms_wide_type]])
2. 種2が別クラスタに割れている = **series-merge**(連載中なら以後も自動追随。
   ★[[series_merge_last_entry_wins]])
3. 予約ドラフト出身の頁 = **preorder-pages の yml へ直接追記**([[preorder_page_zokkan_direct_append]])
4. `★別レーベル` の実例 = ドラベース(種2=てんとう虫C / 頁=コロコロC)、魔法科 侵攻編(電撃C NEXT /
   頁=Gファンタジー=別コミカライズ疑い)、臨場(日本文芸社 / 頁=芳文社)、キャッツ❤アイ21(Bunch world)、
   Age,35 3巻(My first casual=コンビニ本)、凄ノ王7巻(版が3つに入り組む)。
5. 反映のたびに **巻が減っていないか**を確認(promote の `減少なし` 行と消滅ISBN行)。

**Why:** 69頁は一括では裁けず、種2の分裂・版違い・コンビニ本が混ざる。表の目安で分けてから触る。
**How to apply:** 「見なおしの N と M なおして」= 表の **#列**。 触る前に生成器を1回回す。
関連: [[method_bangai_vs_shiryouhon]] [[feedback_raw_count_is_not_worklist]] [[imprint_label_leak]]
