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

## ★2026-09-24 追加: 楽天題の「巻ノN/巻之N/其ノN/第N集/(N集)/(v.N)/(N(副題))」も読めていなかった(当世幻想博物誌)
ユーザ「楽天にあるのに何故発見できない?」= 楽天題『当世幻想博物誌（巻ノ1）』を `_rakuten_match_lib.parse_vol`
(巻抜け充填・題+巻照合など**20本**が共用)が巻番号なしの別題にしていた。巻抜け仮想の**検出**は拾えていた=**埋める段**で落ちた。
- 是正(commit 66465021c): parse_vol に上記規則を**後段に足した**(旧4規則が外れた時だけ見る)。
  楽天ローカル種37.3万件で**旧結果の変化0件・新たに読めた2,813件**を突合で確認してから入れた=この検算を型にする。
- 再充填で APPLY 7(猫柳田(第2集)=今回の規則分1 / 鬼太郎1985年版6=別理由)。
- ★**同じ穴が日次蒸留側にも残っている(未着手)**: `split_title` は上の5表記を全部 vol=None にする
  (= 将来その表記の新刊が新作1巻として別頁化しうる)。直すなら上の「3箇所」+ 負テストとして本番7頁(裸ローマ数字)。
- 副産物: `_volgap-apply-fill.py` が route=overrides を種4へ落としていた(=黙って効かない)→ override 本体へ書くよう修正。
