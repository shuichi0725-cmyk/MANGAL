---
name: anime_flag_freshness
description: "アニメ化フラグ更新機構(2026-08-11): anime_adaptedは種3凍結で初回fill以降不変だった→dump relations(ADAPTATION×ANIME)をenrich unionで重ねる+柱⑥後段_anime-flag-delta.py。false化はしない"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-11T00:23:15.645Z
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
- ★逆方向(頁true・dumpアニメ関係なし)=**1,700頁**は false化しない: 種3のAI fillが実写化を
  アニメ化と誤記した型(21世紀少年/自衛隊1549)と AniList側の関係欠落が混在=機械で裁けない。残置。
- 標本10件全部に具体ANIMEノード(TV/OVA/ONA/TV_SHORT)を確認してから適用した(だろう運転をしない)。

関連: [[monthly_distill_real_pipeline]] [[anilist_matching_state]] [[feedback_one_bug_means_a_class]]
