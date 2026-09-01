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

## 続き: 2026-09-02 ゴルゴ13の再録選集15頁/33巻をdrop(ユーザGO)

上の「★教訓」で未実施だった掃引を、ゴルゴに限って実施。索引 69,219→69,204。
台帳 = `docs/production-diagnostics/golgo13-drop-worklist.tsv`(24頁の全裁定・証拠つき)。

- **再録選集13頁**: shorty(8巻)/characters(4)/best of 200(4)/SPECIAL EDITION(5)/現代史の中のゴルゴ13(2)/
  Legend ofゴルゴ13×6/リーダーズ・チョイス×2。★リーダーズ・チョイス2頁は**同一作品の二重頁**
  (2018年版の楽天題が「改訂版「ゴルゴ13」リーダーズ・チョイス」)。
- **コンビニ廉価2頁**: ゴルゴ1983/ゴルゴ1987。★楽天題は「**ゴルゴ13クロニクル(17)(18)**」、
  ser=My First BIG SPECIAL。**頁の題自体が実題でなく、クロニクルの年号サブタイトルの誤採用**だった
  = 題だけ見ても正体が分からない型。
- **keep**: スピンオフシリーズ(銃器職人デイブ/少女ファネット=完全新作)/ゴルゴさんち(セツコ・山田の
  家族ギャグ=別作品)/Dの十字架(井本仁の別作品)。
- **残り**: ゴルゴ13シリーズ(巻52〜104がISBNなしの本編分裂断片、統合かdropか未決)/
  ゴルゴ外の同型4頁(時代劇画ワイドセレクション11巻・短編セレクション・劇画1964ゴリラコレクション・
  ビッグコミックセレクション名作短編集=多著者アンソロジー)/ゴルゴと呼ばれた男(漫画か未確認)。

★**手順の型**(次に同種をやる時はこれをなぞる):
1. `_skey`を種2から引き `data/seeds/non-manga-drop.yml` に series_key で登録(**恒久**)
2. `_check-seeds.py` で lint → `data/slug-aliases.yml` の死にalias削除 → `_gen-redirects.py`
3. `_reflect-targeted.py --drop <stems>` (manga.v2/preview削除+索引remove)
4. `data/seeds/pending-r2-prune.jsonl` に積む
5. ★**検算**: `_promote-bulk-v2.py --only <1件>` で `dropped_non_manga:1 / regenerated:0` を確認
   (seed登録が効いていないとフルpromoteで全部復活する)
