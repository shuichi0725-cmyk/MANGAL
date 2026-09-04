---
name: urusei-version-display-rules
description: うる星やつらが示す版/巻/刷タブ表示の正規ルール。新刊・新作ページ生成時に適用する基準
metadata: 
  node_type: memory
  type: reference
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

うる星やつら = 多版表示の**正規モデル**。新manga ページ生成(蒸留の型1/2/3)で**この巻選び・版・刷タブ規則を適用**する。実装 = `scripts/_regroup-versions.py` + `data/seeds/editions-supplement.yml` の urusei エントリ。

## ① 巻の選び方（どれを代表に出すか）
- 各 edition は **完備最古**（最も巻が揃った最古の版/刷）を既定表示にする。
- 同じ巻番号に複数ISBN(別刷/同日competeなど)があれば、promote の `_dedup_key`（最古日→支配ISBN線→最小ISBN）で1つ決定的選択。

## ② 違う版の扱い（別editionタブ）
- **type が違う、または 冊数が違う = 別の版** → 別の edition タブで並べる。
- うる星例: 通常版(standard 全34巻) / ワイド版(wideban 15巻) / 文庫版(bunkobon 18巻) / 復刻BOX(aizoban 4巻) = 4タブ。
- edition label = `{type表示名}（全{冊数}巻）`。
- ★edition key は (type × 出版社prefix)＋衝突時edition_id（[[edition_separation_systemic]] の確定アルゴリズム）。type単位だけだと別社standard多版が潰れる。

## ③ 同じ冊数の本の出し方（刷タブに畳む）
- `_regroup-versions.py`: 同一作品内で **(type, 冊数) が一致する版 = 同内容の別刷/別社** とみなし、**1 edition の `versions[]`(刷タブ)に畳む**。単独版はそのまま。
- うる星例: 初版(少年サンデーC 34巻) + 新装版(34巻) → 両方 standard×34 → 「通常版（全34巻）」1タブ＋**刷タブ2**（初版/新装版、古い順）。
- 刷タブ label = edition.label(初版/新装版等) → 無ければ publisher → `版N`。

## 適用先
- 蒸留の **型1 新刊巻**: 既存作の正しい edition/刷 に新巻を挿す（巻選び②③が効く）。
- 型2/型3 新作: 新ページを上記規則で組む。
- 関連: [[multi_edition_unification_pending]] / [[version_tabs_stock_ebook]]（既定=完備最古）/ [[edition_mix_same_author_ayako]]（奇子型=同著者版違い混在の分離）。

## ★冊数違い=版タブ(versions[])で纏めるな(2026-07-08 ユーザ再指摘)
- **同冊数=versions[]刷タブOK**(レイアース=オリジナル/新装版/CLAMP PREMIUM 全3巻→versions[])。
- **冊数違い=別editionタブ(editions[]配列)**にする。versions[]に詰めるのは誤り(タッチ=通常版26/ワイド11/文庫14/完全版12を別editions[]タブ)。
- ★私のミス: 堕靡泥(完全版9/原作7/新装版3)・ショーイチ(完全版24/原作9)を冊数違いなのにversions[]に詰めた→別editionタブに是正。
- ★楽天は原作の書影付きISBNを持つ(ショーイチ本編9巻=NDL欠のvol8含め全ISBN+書影)。Type B再構築は**NDL TSV(全版)+楽天(書影/欠ISBN)+Wiki(正典巻数)**の3点で。

## ★版ブロックの並び順 = 正本ルール (= 2026-09-04 ユーザ裁定で確定。実装 `components/VolumeRow.tsx` の `displayBlocks`)
履歴が3転している(4a77d4e03 初版を上→bb4e6e8d6 書影が揃った版を上→918d3cbb8 9割閾値)ので**この順が現行の正**:
1. **書影の充足で3段**(全巻 or 9割以上=2 / 一部=1 / ゼロ=0)、上の段が上。
2. 同段の中は **1巻の発売日が古い順**(同着は巻数が多い方)。
3. ★**最古の版が「揃っていない」(tier<2)ときだけ**、その版と **同じ冊数** で書影が揃っている版
   (=同じ巻割りの新装版/復刻)を **先頭に引き上げる**。同じ冊数の代替が無ければ 1+2 のまま。
   = ユーザの言葉「最初に発売された物の書影が無い場合はおなじ巻数の書影がある物が一番上。
     無ければ書影がある物の上から発売された順」。
- うる星: ワイド版(15巻)が先頭だったのを **通常版 新装版(全34巻)** が先頭へ。初版(書影0)は最下段のまま。
- 全70,413頁シミュレーションで順序が変わるのは **30頁**(タッチ/X/鉄腕アトム/リボンの騎士/アドルフに告ぐ 等)。
  ★並び規則を触る時は必ずこの全頁シミュレーション(旧sort vs 新sortのlabel列比較)を先に回す。
