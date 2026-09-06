---
name: unlisted_volumes_review_state
description: 【進行中】「頁は在るのに巻だけ出ていない」①の裁定=見なおし表72頁のうち2頁処理済み・残70頁。previewは①セットが入っている
metadata:
  node_type: project
  type: project
---

2026-09-06 開始。 検出器 = [[unlisted_volumes_trinity_type]]。

## いまの状態
- **preview = ①のセット72頁**(無作為3,000頁セットは退場済み)。 巻抜けフラグが立つのは9頁。
- 裁定用 = `docs/production-diagnostics/shu2-unlisted-review.tsv`
  (1行1頁: 公開slug / 作品 / 欠けている巻 / 種2のimprint / 頁の版 / **判定の目安** / ISBN)。
  判定の目安 = `同レーベル=素直な取りこぼし` 38頁 / `★別レーベル=版タブ・別作品を先に判断` 32頁 /
  `★誤番号` 2頁(一騎当千1000巻・こち亀999巻)。
- **処理済み 2頁**(表のヘッダ込み5・6行目):
  - 悪役令嬢後宮物語～王国激動編～ 6,7巻 → series-merge(3sid統合)。 全7巻
  - エイリアンヘッドバット 2巻 → preorder-pages へ直接追記。 全2巻
- **残り70頁**。

## 次にやる時の型
1. `同レーベル` から。 種2のimprintが頁の版と一致するものは素直に足せる。
2. 足し方の分岐: 通常頁= **種4**(imprintを頁の既存版に合わせる。 合わせないと幻の版ができる) /
   種2が別クラスタに割れている= **series-merge**(連載中なら以後も自動追随。 ★[[series_merge_last_entry_wins]]) /
   予約ドラフト出身の頁= **preorder-pages の yml へ直接追記**([[preorder_page_zokkan_direct_append]])。
3. `★別レーベル` は版タブ/別作品/非掲載の判断が先。 実例= ドラベース(種2=てんとう虫C / 頁=コロコロC)、
   魔法科 侵攻編(電撃C NEXT / 頁=Gファンタジー=別コミカライズ疑い)、 臨場(日本文芸社 / 頁=芳文社=別出版社)、
   キャッツ❤アイ21(Bunch world版)、 Age,35 3巻(My first casual=コンビニ本)、 凄ノ王7巻(版が3つに入り組む)。
4. 反映のたびに **巻が減っていないか**を確認(promote の `減少なし` 行と消滅ISBN行)。

**Why:** 72頁は一括では裁けず、種2の分裂・版違い・コンビニ本が混ざる。表の「判定の目安」で分けてから触る。
**How to apply:** 「見なおしの N と M なおして」= この表の**ヘッダ込みの表示行**番号。
関連: [[volgap_leading_gap_and_frozen_input]] [[method_bangai_vs_shiryouhon]]
