---
name: drop_batch_2026_09_01
description: 2026-09-01にユーザGOで16頁を非掲載drop(廉価再編集/傑作選/アンソロ/ムック/合本/アメコミ邦訳)。★教訓=本番のimprintは化けるので楽天seriesNameで判定する
metadata: 
  node_type: memory
  type: project
  originSessionId: ffbe783f-3849-4cd8-936a-578c71df6d9a
  modified: 2026-09-01T13:21:35.885Z
---

外部エンリッチの過程で溜めた掲載境界を、ユーザ裁定でまとめて落とした回。索引 69,235→69,219。

## 落としたもの(16頁)と決め手

- **コンビニ廉価/再編集**: 泣ける!ゴルゴ13 / Epic of ゴルゴ13 / 蒼太の包丁deluxe / HAL'S MOTO
- **アンソロジー(著者欄が「アンソロジー」「◯◯編集部」「出版社名」)**: 旅情ミステリースペシャル / 浅見光彦ミステリー&旅愁サスペンス / コミック名探偵浅見光彦 / コミック赤川次郎ミステリー / ジャンプSQ.Comic Selection / マジキュー4コマ STEINS;GATE
- **傑作選(subTitleに「傑作選/傑作集」)**: 読者投稿心霊体験 / ワタシの川原泉
- **ムック(seriesName=◯◯mook/集英社ムック)**: キン肉マンジャンプ / GIANT KILLING extra
- **合本(巻題が「(1＋2巻)」)**: お徳用毎日かあさん
- **scope外**: インビンシブル・アイアンマン:アイアンハート(アメコミ邦訳・ShoPro Books)

同日、別ルートで **リリパット**(東京三世社の同題アンソロジー7クラスタ)と **月刊こち亀ほか5頁**も処理済み。

## ★教訓: 本番のimprintは化ける

『泣ける!ゴルゴ13』は楽天seriesNameが **My First BIG SPECIAL/SUPER**(=CLAUDE.mdのdrop imprint patternsに明記済のコンビニ廉価レーベル)なのに、
本番頁のimprintは `Golgo 13 special` になっていて**既存の網をすり抜けていた**。
→ **imprint文字列だけの網は信用しない。楽天の seriesName / author / subTitle を見る**。
同型が他にも眠っている可能性があり、「楽天seriesNameがMy First BIG系なのに本番imprintが違う頁」の掃引は未実施。

## keepにしたもの(一貫性のため)

- **オリンポスの咎人** = ハーレクイン原作シリーズの連作コミカライズ(巻ごとに作画者が違うだけ)。ハーレクインコミックスは本番に95頁が通常掲載されているため落とさない。
- **今でも忘れられないアノ体験談、話します** = 【廉価版】表記はあるが「再編集/傑作選」の一次情報が取れず据え置き。

関連: [[external_enrich_state]] [[konbini_reprint_sweep]] [[bunsatsu_gappon_exclusion]] [[non_manga_drop_cleanup]]
