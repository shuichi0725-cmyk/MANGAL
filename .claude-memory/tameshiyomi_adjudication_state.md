---
name: tameshiyomi-adjudication-state
description: "試し読み(BookLive)裁定=枯れ達成(2026-07-18): アンカー25,149・保留9,749は全分類済み。台帳=docs/production-diagnostics/tameshiyomi-adjudication.jsonl(5,644件)が次回roundのskip基準"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

## 到達点 (2026-07-18 「枯れるまでやって」完遂)
- **アンカー25,149 slug**(seed=data/seeds/tameshiyomi-booklive.jsonl)。全巻展開15,135巻。
- compare最終 = **accept 0 / ambiguous 0 / 不一致確定 0** = 機械・目視とも掘り尽くし。

## 裁定装置 (scripts/_tameshiyomi-adjudicate.py)
- fetch-meta = 候補tidの商品頁(vol_no/001)を直GET→og:title+著者を .cache/tameshiyomi-tid-meta.jsonl に貯める(再開可能)
- compare = 実題×頁題+著者の決定的突合 → accept/ambiguous/mismatch三分。台帳skip内蔵。
- 採用は `_tameshiyomi-harvest.py --accept-file`(HEAD200ゲート込み)

## 保留9,749の最終内訳 (全て分類済み・再調査不要)
- 不一致確定(実頁照合済) 5,253 / 候補0(BookLive未配信) 3,531 / 候補全滅(商品頁403=削除済・再試行でも403=恒久) 574 / 目視保留 391(分冊・合本のみ/別作候補/シリーズ起点不明)
- ★台帳 = **docs/production-diagnostics/tameshiyomi-adjudication.jsonl**(git永続化済み。.cache正本の鏡)。次回roundはこのslugをskip=枯れ判定の核。

## 目視の裁定ルール (確立済み・次回も踏襲)
- 完全一致(巻尾のみ許容)+著者一致=採用。モノクロ>カラー(元カラー作はカラー可)/単行本版>連載・分冊/完全版・新装版・文庫版OK。
- 分冊のみ・合本のみ・話売りのみ・タテヨミのみ=保留。別作・続編・スピンオフ候補=保留。同題2tid判別不能=保留。
- 表題筆頭の合本(例「ケセランパサラン/ロマンスの泉」)で唯一の電子形=採用(2026-07-18確立)。

## 教訓 (再発防止)
- ★holds TSVの候補JSON [:200]切り詰めで9,674保留が評価不能化していた(修正済み=全量書く+regex tid救済)。**簿記の切り詰め禁止**。
- 同一tidを複数頁に貼らない(アルプス伝説型: 無印頁と黄金頁→正確一致側だけ)。

## 次の食い扶持
- expandバックログ(923/1,089シリーズ完了=残166シリーズの巻展開)=アイドル運転柱①。
- BookLive未配信3,531は電子化され次第候補が生まれる(再discovery時のみ)。
