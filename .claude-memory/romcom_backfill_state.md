---
name: romcom_backfill_state
description: "【進行中】ラブコメ復権=romance∩comedy 7,184作をromcom裁定。判定=skill romcom-judge(Sonnet)・適用=Opus+。台帳2,581済/残~4,600"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-02T23:44:58.676Z
---

★**romcom枯れ問題**(2026-08-03 ユーザ発見「80年代のラブコメが6件」): romcom は全DB143作のみ。
根因=注ぎ手(AniList/楽天/AI fill)が romance+comedy に割って romcom を出力しない構造。
候補=**romance∩comedy 7,184作**(80s=362)。ユーザ裁定=方式1(AI裁定バックフィル)→ コスト配慮で
**skill化して安い運転に委譲**(2026-08-03「あなたがやるとコストで困るかも。skill化して他にやらせたい」)。

## 現在地

- 自動YES(紹介文「ラブコメ」明記)= 2,181件 / AI裁定済 400件(yes46/no83/unknown271) / **残 ~4,600件**
- 台帳 = `data/seeds/romcom-judged.jsonl`(git追跡・純粋追記・冪等)。worklist = `.cache/romcom-worklist.jsonl`(再生成可)
- **正本 = skill `romcom-judge`**(判定=Sonnet・材料ベースfail-closed・知識判定禁止 / 適用=Opus+が `_romcom-apply.py`)
- 適用先 = `genre-append.yml`(union・フラグ不変)。反映は件数多なら週次に乗せる。
- ★Opus+の残タスク: 材料無しunknown層のうち**知名作の知識判定**(タッチ/ラフ等の型は初期400件で実施済)。

## 横展開(効果確認後)

同型の「注ぎ手がいない枯れキー」: **4-koma 93**(数千あるはず・レーベル/楽天タグに強信号)/ gag 147 /
samurai 132 / mahou-shoujo 217 / war 194 / yokai 257。候補集合の作り方は各キーで別設計。

関連 [[genre_append_seed_mechanism]] [[ai_genre_closed_vocabulary]] [[genre_quality_improvement]]
