---
name: sansedai-featured-stock-state
description: 三世代/今週の一冊ストック=生成済み(741+55件)だが未配線。場所・人格・再生成手順
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

三世代(6人格コラム)+今週の一冊(週刊特集)の**コメントストックを生成済み**(2026-06-14)。
**ストックのみ=ページ配線/公開はまだしていない**(ユーザ指示「1ストックだけ」「3まだ公開してないのでストックだけ」)。

- **場所**: `data/seeds/sansedai-stock.yml`(entries: persona/gen/slug/title/comment 741件)/ `data/seeds/featured-stock.yml`(entries: slug/title/author/blurb 55件)。
- **人格6人**(home-design-11 WRITERS と一致): gen0 ミナト(10-20代)/リコ(美大生・作画重視); gen1 サオリ(30-40代)/タケル(元書店員); gen2 圭三(古書店主)/静江(喫茶店ママ)。人格別116-128件で均等。
- **生成方法**: 分散Workflow。人気上位1800作(`scripts/_build-sansedai-worklist.py`=popularity粗フィルタで高速化、TSV)を600ずつ3ティアに分け、各ティアを6スライス×6人格=36体(三世代)+6体(今週)で並列。各体は担当スライスを Read し、適合作のみ人格ボイス短評(ネタバレ無し)。schema構造化出力。
- **取込**: `scripts/_write-stock-from-workflow.py <task出力json>` = slug実在検証(data/manga.v2)・HTMLエンティティ除去・persona×slug dedup・純粋追加。
- **未了(次フェーズ)**: ページ配線。home-design-11 の三世代は現状ハードコードWRITERS(6件)→このシード駆動に切替要。今週コーナーも未実装。三世代の過去ログ(/sansedai-archive)も。比率=三世代:今週=7:1(日替わり vs 週刊)。
- 関連: [[ai_review_league_operation]](別企画=AI書評家リーグ)/ display polish。
