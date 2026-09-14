---
name: volume-marker-blindspots-latin-roman
description: 巻表示がラテン(VOLUME N)や全角ローマ数字(Ⅻ)だと分離器の全規則をすり抜け、既刊のN巻が「新作1巻」としてドラフト化される型
metadata:
  node_type: memory
  type: project
---

予約ドラフトの分離器(`_preorder_title_lib.split_title`)は巻表示を**算用数字か漢数字**の前提で書かれているため、**ラテン表記の巻表示**が素通りして `vol=None` → **新作1巻**として別頁化される。2026-09-14 の日次蒸留で2型を実踏し、両方 script に焼いた(手順は skill `daily-distill` の「2026-09-14 の恒久修正」が正本)。

- **VOLUME N / VOL.N 型**: 痛覚探偵 通天寺ナツメ […] VOLUME 2 TWO(1巻 9784040763477 が実在)
- **全角ローマ数字型**: 部長の夜テク…（Ⅻ）= 12巻(既存頁は1-11巻在り)。★**Ⅻ は NFKC で "XII" のラテン文字になる**のが罠

**Why:** これは [[never_delete_because_broken]] の逆向きの事故で、単巻先行登録禁止([[new_manga_registration_order]])を機械が破る経路。頁が2つに割れてから気づくと統合コストが高い。

**How to apply:**
- ★**巻表示の規則を足す箇所は1つではない**。最低3つ: ①`split_title`(番号を読む) ②`_preorder-gen-midfill.py` の `VOLP`(題base→全巻の逆引き。ここが抜けると「全巻回収不成立」でhold) ③`_preorder_draft_lib` の `_VOL_TAIL`/`_VOL_KANA`(題とヨミから剥がす)。1つ直して通ったつもりになると次の関門で別の症状が出る
- ★**裸のローマ数字は題の一部**(エコエコアザラクⅡ/Arc The Lad Ⅱ/FINAL FANTASY Ⅻ/闘神都市Ⅲ 等 本番7頁)。**括弧付きだけ**採り、1文字(I/V/X)は suspect 止まりにする。新規則は必ずこの7頁で負テストする
- 検知の入口= 出荷前レビュー(`_preorder-review.py`)の **CONTINUATION** 行と、索引skip調査。今回は索引skip(publisher未登録)を追う過程で(Ⅻ)に気づいた=**別の検出器が拾った異常の周辺を見る**のが効く
- 関連: [[feedback_one_bug_means_a_class]] [[subtitle_orphan_volume_split_sugar_spice]]
