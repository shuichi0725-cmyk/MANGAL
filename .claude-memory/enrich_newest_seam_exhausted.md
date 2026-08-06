---
name: enrich_newest_seam_exhausted
description: "【重要】エンリッチ「新しい順」柱は2026-08-06に鉱脈が枯れた。残バックログ12,057頁のうち1〜2巻に使えるcaptionがあるのは0件(全走査で確認)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 164c5cf9-b3fb-40f8-a19c-7cc4f6403843
  modified: 2026-08-06T11:37:51.364Z
---

2026-08-06 の連続運転(20スライス指示)で判明した**構造的な壁**。

## 実測(推測でなく全走査)
- `.cache/enrich-newest-backlog.tsv`(catch/syn欠け×2巻以上、最新巻の発売日降順)の**残り12,057頁を
  楽天キャッシュで全走査**(live照会0回・`_enrich-captions.py --slugs ... --src data/manga.v2`)。
- **60字以上のcaptionが1件でもある頁 = 138**。そのうち **1〜2巻のcaptionがあるのは 0件**。
- live照会でも歩留まりは落ちる一方だった: 2026年帯=材料44〜50%/100頁 → 2023年帯=**材料14/120、
  うち1〜2巻のpremise記述があるのは1件**(「BLコミック」「侍VSゾンビ 上」「1」のような書名だけのcaptionが大半)。

## なぜか
バックログは**最新巻の発売日で降順**に並ぶ。上澄み(2026年の新刊頁)を消化し終えた残りは
「最新巻が2023年以前 = とっくに完結した長期連載」であり、楽天は**近刊にしかitemCaptionを持たない**。
= 残りは「後半巻のcaptionしか無い」か「captionそのものが無い」。

## 帰結(次にやる人へ)
skill `enrich-catch-synopsis` の**楽天caption一本足では、この柱はもう伸びない**。選択肢は3つ:
1. ★**後半巻captionから premise だけを抜いて書く**(skillの「文面は1〜2巻の範囲」を緩める)。
   実際 138頁の多くは巻ごとにシリーズ前提を再掲している(例 猫耳少女/ニア・リストン)。ユーザ裁定が要る。
2. **材料源を替える**(NDL書誌の内容細目 / Wikipedia)。skill外の新柱になる。
3. **この柱を止める**。残りは「材料が無いので空のまま」が skill の既定方針でもある。

## この日の実績
batch 9204〜9214 で **321作**適用(catch+321 / syn+310 / genre+265・上書き0)。
hold台帳 `docs/production-diagnostics/enrich-hold.tsv` に **265件**を理由付きで退避。

## ★仕組みの穴を1つ塞いだ
`scripts/_enrich-nomat-hold.py` を新設。**harvestしたのにcaptionが無かったslugは done にも hold にも
入らず、バックログ先頭に永久に居座って毎周live照会だけを浪費していた**(実測: 115頁harvestで材料9件、
残りは全部この再照会分)。harvest直後にこれを走らせて hold へ退避する。

関連: [[enrich-7k-resume-state]] [[catch_synopsis_enrich_pending]]
