---
name: tagless_coverage_next
description: 【残タスク・次回】要素タグなし32,609作(1990s-2010s中心)を埋める。楽天タグの対象拡大(中精度タグの2パス救済)or閾値緩和。genre側の残provisionalも同様
metadata:
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★**次回やる(2026-06-17 ユーザ指示「今度ここをやる覚えておいて」)**。[[genre_from_rakuten_story_plan]] の続き。

## 対象
本番 manga.v2 の **要素タグなし 32,609作**。年代別(year_started)= 〜1969:188 / 1970s:514 / 1980s:4,055 /
1990s:7,863 / 2000s:8,201 / 2010s:8,255 / 2020s:3,533 / 不明:0。
→ **古い作品の問題ではなく 1990s〜2010s(各8千前後)に集中** = 新しめにも広く欠けている。

## 原因
AniList未照合(タグ源なし)+ 今回の楽天タグを「高精度26種・本文に明確な根拠あり」に絞ったため取りこぼし。

## 次の手(どれか/併用)
1. **楽天タグの2パス救済**(genre版Phase④のタグ版・未実施): 中精度タグ(Reincarnation/Crime/Time Manipulation/
   Medicine/Gender Bending/Survival/Royal Affairs等)を gray から本文で厳格再判定→確証分だけ追加。
2. **閾値緩和**: 採用タグを増やす(較正の P目標を下げる/medium採用を広げる)。
3. **caption無し作**は楽天では届かない → 別源(NDL/Wikipedia/AniListタグ再照合)が要る。

## 流用できる資産(再生成不要)
- 分類済予測 `.cache/genre-rakuten/target-out/`(genres+tags+conf、20,682作)= **再分類せず gray から救済可**。
- gray候補 `.cache/genre-rakuten/gray-candidates.jsonl`(tags_gray 含む)。
- 較正 `phase2-calibration.json`、tag語彙 `tag-vocab.json`、台帳 `docs/genre-rakuten-learning.md`。
- 反映は方法D `_genre_rakuten_apply_inplace.py`(tag-rakuten.yml に union 追記→再実行)。

## genre側の残
provisional(AI暫定のみ)も **25,529作** 残(うち other単独~1,056)。楽天で届かなかった分。同様に救済余地。
