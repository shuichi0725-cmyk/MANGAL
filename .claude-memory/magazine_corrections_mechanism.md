---
name: magazine_corrections_mechanism
description: 【新設】掲載誌の per-case 上書き seed = magazine-corrections.yml。種3のmagazineは根拠なしのAI fillで誤りが多い。スーパージャンプ調査で空欄106/別誌20を検出(未着手)
metadata: 
  node_type: memory
  type: project
  originSessionId: 164c5cf9-b3fb-40f8-a19c-7cc4f6403843
  modified: 2026-08-07T00:51:21.710Z
---

2026-08-07 新設。夢幻の如く(スーパージャンプ連載)が `weekly-young-jump` になっていた件から。

## 機構
- **`data/seeds/magazine-corrections.yml`**(slug→{magazine, source, evidence, added_at})。
  promote が `_MAG_CORR` で読み、種3/brand推定より**最優先**で上書き。
- ★値は **`data/magazines.yml` のキー**であること。未登録キーは**警告を出して無視**する安全弁つき
  (誤キーが本番に漏れない)。スーパージャンプは雑誌マスターに無かったので `super-jump` を新規登録した。
- なぜ要るか= magazine は種3(series-supplement-v2.yml)のAI fill由来で根拠がない。
  種3は純粋追加only・既存key変更禁止(月次蒸留のabort条件)なので、種3を汚さずここで上書きする。
  **status が同じ理由で不信任され `status-corrections.yml` が作られたのと同型**。

## スーパージャンプ調査の結果(調査のみ・是正は未着手)
worklist = **`docs/production-diagnostics/magazine-super-jump.tsv`**
ja.wikipedia「スーパージャンプ」掲載作品一覧 **144作** × 本番の magazine:

| 判定 | 件数 |
|---|---|
| super-jump 済 | 1(夢幻の如く=是正済) |
| **magazine が空** | **90**(題+著者が完全一致) + 16(著者から引き当て) |
| **別の雑誌が入っている** | **20**(要per-case) |
| 本番に頁が見当たらない | 16 |

★**空欄のほうが圧倒的に多い**(106件)。「誤った雑誌」より「そもそも埋まっていない」が主症状。

## ★20件を一括上書きしてはいけない理由(実地で確認)
- **移籍**(両方とも事実): ふんどし刑事ケンちゃん・赤龍王・マーダーライセンス牙 = 週刊少年ジャンプ→スーパージャンプ。
  magazine は1つしか持てないのでどちらを出すかは判断マター。
- **頁の粒度違い**: 「コブラ〜聖なる騎士伝説」は本番 `cobra`(COBRA本編・WSJ)に含まれる。
  「世紀末リーダー伝たけし!完結編」も本編頁に吸われている。
- **同名別作の疑い**: `zero`(ビッグコミック)・`jin`(ヤングジャンプ)が本当に同じ作品か未確認。
- 明らかに直すべき分= GOLDEN BOY/世紀末博狼伝サガ/緋が走る/銀のアンカー/ふぐマン/トクボウ朝倉草平 等。

## 横展開の余地
雑誌記事の「掲載作品一覧」×本番magazine の突合は**どの雑誌でも同じ手順で回せる**。
手順= Wikipedia掲載作品一覧をWebFetch → `.cache/prod-title-mag.tsv`(全頁のslug/題/magazine/著者を1パス)と
題+著者で突合 → 空欄/別誌/未特定に3分類。題の表記差は**著者軸で引き直す**と拾える(JIN・バーテンダー等が
題の完全一致では落ちた)。

関連: [[data_assets_inventory]] [[feedback_accuracy_is_the_goal]]
