---
name: harvest_based_fix_mechanism
description: 【次の中核作業】楽天harvest完了→発売日逆行/巻抜けの是正に「題+巻番号→楽天item照合」機構が要る。item構造と罠
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

楽天harvest完了(2026-06-27・全47,922著者)。次は是正キュー消化だが、その**共通機構**を先に作るのが本筋。

## 楽天harvestデータ(全item入ってる=捨てない)
- `.cache/rakuten-isbn-delta.jsonl`(**828MB・571,858行**)。形= `{isbn, item}`。
- item の全フィールド: `title/titleKana/subTitle/subTitleKana/seriesName/seriesNameKana/contents/**author/authorKana**/publisherName/size/isbn/**itemCaption(=説明文)**/**salesDate**/itemPrice/listPrice/discountRate/discountPrice/itemUrl/**affiliateUrl(書影/リンク)**`。
- 発売日(`release-date-full.json` 168,861 ISBN)はcommit済。旧`rakuten-isbn.jsonl`(245k・06/18)は新と独自10.4%(25,571)→**merge必要**(union 373k)+永続化の家(Drive等)。

## ★核= 「題+巻番号 → 楽天item照合」機構(発売日逆行・巻抜け・両方が要る)
- **発売日逆行(515・`docs/volume-date-disorder.tsv`)**: 我々のISBNは再版なので**ISBN照合では再版日のまま**(同ISBN=同日)。初版を取るには **題+巻番号で楽天の全printingを照合し最古salesDateを採用**。
- **巻抜け(647・`docs/volume-gaps.tsv`)**: 欠番の巻を **題+巻番号で楽天から見つけてISBN取得→種4(volumes-supplement.yml)**。
- ★**罠**: ゴルゴ13は題が**全角「ゴルゴ１３」**等→**NFKC正規化必須**(halfwidth抽出で0件だった)。巻番号parse=末尾数字/（N）/「N巻」/vol.N。題の表記揺れ(SPコミックス等subtitle)も吸収。
- catch/説明補完(19,750・`missing-catch-synopsis-2000plus.tsv`)も **itemCaption** が使える(B後)。

## 順番(ユーザ指定)
A: 発売日逆行→巻抜け（この機構で）→ B: NDL典拠ID取得(同名異人分離・[[acquire_all_obtainable_info]]の抜き忘れ回収)。
★慎重に([[feedback_dont_repeat_regrouping_error]]): 多数決/可逆/小バッチ/dry-run。関連[[volume_date_disorder_list]][[catch_synopsis_enrich_pending]]。
