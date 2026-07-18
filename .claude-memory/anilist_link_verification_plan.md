---
name: anilist-link-verification-plan
description: "【計画】AniListリンク検証(トリガー=AniListリンク検証やって): ①検証ゲート新設→②疑惑3,967裁定→③recall上積み。誤情報を消すのが先、リンク増は後(2026-07-18ユーザ合意)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

## 背景 (2026-07-18 ユーザ問題意識)
「AniListは有効だが誤マッチが問題」。現状=matcher v14で~44%マッチ・監査で疑惑3,967件(~10%)リスト済み([[anilist_link_quality]])。
方針合意: **誤マッチ潰し(precision)が先、マッチ増(recall)は後**。低信頼リンクはenrichを剥がす=誤あらすじ/誤ジャンルを出すより空([[feedback_accuracy_is_the_goal]])。

## 実行順 (トリガー「AniListリンク検証やって」)
1. **検証ゲート新設**: 全リンクに独立証拠の合議スコア
   - 巻数(AniList volumes vs 頁巻数、完結作±1) / 開始年(startDate vs year_started ±1) /
     著者(staff姓 vs 頁著者。kana35,679+.cache/anilist-author-surname.json) / 状態(FINISHED vs 完結)
   - ★正解チャネル=**Wikidata P8731**(作品QID→AniList ID公式対応、.cache/work-qid-map.json 5,754作)。矛盾リンクは機械付替可
   - 低信頼はenrich join を止める(promote時ゲート or enrich-map生成時に除外)
2. **疑惑3,967件の裁定**: P8731自動付替→残りをAI目視スライス(試し読み裁定と同じ型=index→判定→一括適用)
3. **recall上積み**: 著者経由23,304([[anilist_matching_state]])+P8731直結線+synonyms改善。AniListに無いロングテールは構造的天井=素材ハーベスト(wiki/楽天)が受け皿で正

## 素材の所在
- dump=.cache/anilist-manga-dump-v3.jsonl.gz(5/31)+delta=.cache/anilist-delta.jsonl(柱⑥が随時収集、mergeはOpus専権=[[idle-run]]skill)
- 疑惑リスト=.cache/anilist-link-suspects.tsv(6/13生成。着手時に鮮度確認・必要なら再監査)
- enrichマップ=.cache/anilist-enrich-map.json(7/8)・生成器=_build-anilist-enrich-map.py
