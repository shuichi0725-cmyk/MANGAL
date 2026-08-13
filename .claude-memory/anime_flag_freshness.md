---
name: anime_flag_freshness
description: "アニメ化フラグ更新機構(2026-08-11): anime_adaptedは種3凍結で初回fill以降不変だった→dump relations(ADAPTATION×ANIME)をenrich unionで重ねる+柱⑥後段_anime-flag-delta.py。false化はしない"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-13T11:05:16.354Z
---

2026-08-11 ユーザ指摘「アニメ化情報はanilistから最初作った後変わってない気がする。更新する仕組みが無いなら問題」→実際に無かった。

## 判明した構造
- `anime_adapted` は **種3(series-supplement)の初回AI fill(2026-05)にしか無く**、種3不変原則で以後更新ゼロ。
- 柱⑥(_anilist-delta.py)が dump の鮮度を保っても、relations→頁フラグの配線が無かった。

## 恒久機構(3点)
1. `_build-anilist-enrich-map.py` が relations の **ADAPTATION×ANIME** から `anime:true` を抽出(enrich map再生成時)。
2. promote が enrich の anime を **union**(種3/srcがfalse・無印でも true を重ねる。★false化はしない)。
3. 柱⑥後段 = `scripts/_anime-flag-delta.py`: dump+delta last-wins で再計算→enrich mapへパッチ→
   未フラグ頁を `.cache/anime-flag-worklist.txt` に列挙→ reflect-targeted で適用(~400頁/バッチ)。

## 初回実測(2026-08-11)
- dump104,887+delta85,164行 → アニメ化あり3,878 aid / enrichパッチ3,817件 / **フラグ立て漏れ821頁を適用**。
- ★逆方向1,700頁=**2026-08-11 裁定完了**(ユーザ指示「ここ直して」): 4層ゲートで機械裁定→
  true維持1,052(直接関係725+franchise281+今期seed46) / HOLD19(題一致12+wiki7=真アニメだが
  リンク先entryに関係なし=**リンク修理候補台帳** docs/production-diagnostics/anime-flag-holds.tsv) /
  **false化629**(wiki実写のみ56/wiki無記述29/素材なし544。不確実な高人気2件=十字架のろくにん・
  すべ破はWeb裏取りでアニメ無し確認)。false化= `data/seeds/anime-adapted-overrides.yml`(false_slugs)、
  promoteで **enrichの前に適用=enrich後勝ち**なのでAniListに関係が付けば自動true復帰(自己修復)。
- 標本10件全部に具体ANIMEノード(TV/OVA/ONA/TV_SHORT)を確認してから適用した(だろう運転をしない)。

## 空振り事故と根治(2026-08-13)
- 症状(Sonnetアイドル報告): 適用したはずの17頁(atagoul/死角/Tokyo tribe等)が毎回worklistに再出現、
  「反映して」も頁が変わらない空振り。
- ★根因= worklistの元 `.cache/anilist-to-slug.json` が **7/12製の古マップ**(頁ymlのanilist_id逆引き)。
  7/18のリンク検証で頁から剥がされた誤リンク(続編/外伝/画集/同名異作→親作品entryへの誤結線)が
  マップにだけ残存 → 頁はaid無し=enrich非結線=promoteで何も起きないのにworklistに載り続けた。
- 修正= `_anime-flag-delta.py` が実行時に必ず `--rebuild-map` を先行(組込済)。再構築後の正当worklist
  34頁(SBR/魔探偵ロキ/ユーベルブラット/マシュマロ通信/藤丸立香はわからない等)を反映済=33頁フラグ確認。
- 残per-case 1件: konpaira-fesuta(コンパイラフェスタ・麻宮騎亜全3巻1991-93)= 本編「コンパイラ」(aid32952)
  との題ズレでenrich未結線。頁のaidは旧promoteの焼き残り。NDLで題を確定してから裁定。
- 教訓: **.cacheの導出マップは使う直前に再構築**(seedでないキャッシュは黙って腐る)。

関連: [[monthly_distill_real_pipeline]] [[anilist_matching_state]] [[feedback_one_bug_means_a_class]]
