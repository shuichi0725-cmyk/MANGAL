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

## ✅ 2026-10-02 手1(楽天タグ保留候補の救済)を実施
- 要素0かつ保留候補(gray)あり 7,907頁 → 紹介文(corpus-v2 caption+キャッチ)に**明記語**がある組だけ確定=**3,104頁・のべ3,674件**(書込先 tags-enrich-2425.json・台帳 themes-from-catch-changelog.jsonl stage=gray-rescue)。要素0: 48,450→45,347。
- 抜き取り274件(要素ごと)で適合率約93%。外した要素=執筆/政治/自殺/暗殺者(2/4)。ゲームは「人気ゲームの4コマ/コミカライズ」を除外、性別変化は「男の娘」を語から外す。抽象タグ(Heterosexual/悲劇/成長物語/哲学/癒し系 等)は対象外。
- 道具: `.cache/themes-from-catch/gray_ev.py <stage名>` → `scripts/_themes-from-catch.py apply <stage> --go --model=...`。
- 残: War 354 / Youkai 114 の保留候補は要素語彙に無い(=ジャンル側の語)ので未処理。やるなら genre-append 経由で抜き取り検定から。

## ✅ 2026-10-02〜03 ③④をSonnetが判定・Opusが点検(道具 scripts/_themes-genres-ai.py・指示書 docs/briefs/themes-genres-ai-sonnet.md)
- ③要素: 対象27,817頁(要素0かつ材料あり)→ 7,909頁・のべ9,268件。④ジャンル(汎用だけの頁)15,167頁→1,653頁・のべ1,790件(genre-append.yml・source "full:sonnet-5.5"=一括取消可)。
- 点検: 無作為 ジャンル49/50・要素47/50。型の誤り=**ゲーム原作のコミカライズに要素「ゲーム」**(29件取消)/「〜さながら」「〜を思わせる」架空時代に歴史(2件)。台帳 themes-ai-/genres-ai-changelog.jsonl に stage=full-audit-revert。
- 結果(本番索引): 要素0 48,450→37,471 / 汎用ジャンルだけ 22,871→21,080。残りの大半は材料が無い頁。
