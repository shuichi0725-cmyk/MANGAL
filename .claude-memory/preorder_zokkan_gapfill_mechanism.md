---
name: preorder_zokkan_gapfill_mechanism
description: 【型・機構】楽天予約harvestの窓は「未来〜今日」なので過去に出た巻は構造的に入らず、続巻だけ足すと頁に穴が残る。_preorder-zokkan-gapfill.py で classify後・apply前に機械回収(著者overlapが主ゲート)
metadata: 
  node_type: memory
  type: project
  originSessionId: f534b513-828c-49d6-9d96-41a3da00cc5a
  modified: 2026-09-07T03:00:23.774Z
---

# 続巻適用で欠番が残る型 (2026-09-07 型化・機構化)

`_rakuten-preorder-harvest.py` の取得窓は **「未来〜今日」**(releaseDate降順で今日まで)。
したがって **今日より前に発売された巻は構造的に harvest に入らない**。
そこへ分類器の④緩和一致が「頁max+1..+3」を許すため、続巻だけ足すと**頁に穴が開いたまま公開**される。

実測(2026-09-07 日次蒸留):
- `mogura-no-uta` 土竜の唄: 頁max95(2026-06) に 97(2026-10予約)を足すと **96(2026-08-28刊)が永久欠落**
- `saijo-no-osewa` 才女のお世話: 頁max2(2023-05) に 7(2026-10予約) → **3..6 が欠落**

## 機構 = `scripts/_preorder-zokkan-gapfill.py`(classify後・apply-zokkan前に走らせる)

1. zokkan各行の `_vol` と「頁standard巻 ∪ 種4-auto巻」を比べて欠番を列挙(>12巻は per-case へ回す)
2. 欠番だけ楽天live題検索で回収 → `classified.json` の zokkan に**追記**するだけ
   (以後は既存の全ゲート= slug実在/巻番号/同巻番号既在/series_key逆引き/covers seed追記 をそのまま通る)
3. 楽天に出ない欠番は**埋めずに** `zokkan_gap_open` として triage に残す(捏造しない)

## ★同定ゲートで一番効くのは「著者overlap」

題一致+巻番号だけだと **同題の原作ラノベを混ぜる**。才女のお世話は HJ文庫(原作・坂石遊作/みわべさくら)が
1..12巻あり、コミック(HJコミックス・**水島空彦**作画)3..6 と巻番号が丸かぶりしていた。
→ 頁の `authors`(作画/主著者)とのoverlapを必須に。★`original_authors` は**入れない**
(原作者はラノベ側と共有するのでゲートが無効化する)。レーベル名ゲート(文庫/ノベル)は補助
= HJ文庫1巻は楽天 seriesName が空で、レーベルだけでは弾けない。[[novel_in_manga_page]]

## 同居機能: 先頭欠け補完(`lead_fill`)

分離器は「かな/漢字直後の裸数字」を確定巻にしない(ワイルド7型を壊すため)= `vol_suspect` 止まり。
分類器は suspect>=2 のときだけ巻扱いにするので **suspect==1 の第1巻だけが落ちる**。
実例=「そして誰もいなくなった1/2/3」(ハヤカワ・コミックス・同日3巻同時刊)で 2,3 だけ種4に入り、
新設される通常版タブが**2巻始まり**になった([[edition_lead_gap_atom_type]] と同じ絵)。
ゲート= 同 _slug・同base・同publisher・同ym・同seriesName の兄弟に確定巻が2つ以上あり、
その suspect 番号が兄弟の巻集合の欠番であること。

**Why:** NDL(B柱)は納本後で遅く、月次MADBはもっと遅い。**その日の楽天スナップショットで塞ぐのが一番安い**
(live題検索1〜2回で済む)。穴を放置すると巻抜け監査の母数に流れ込み、per-case の手仕事になる。

**How to apply:** 日次蒸留の手順3(classify)と手順4(apply-zokkan)の**間**に必ず1本挟む。
「題で巻を拾う」仕組みを新設する時は毎回、著者overlapを主ゲートにする。
関連: [[volgap_diagnosis_order]] [[daily_distill_classifier_gate]] [[feedback_one_bug_means_a_class]]
