---
name: genre_append_seed_mechanism
description: 【新設・重要】genre-append.yml=既存genresを消さずunionする唯一の経路。promote結線済
metadata: 
  node_type: memory
  type: project
  originSessionId: 2e629c9e-d55a-4074-a6ec-d0691965d657
  modified: 2026-08-03T01:26:10.821Z
---

**2026-07-31 新設(ユーザGO済)**。`data/seeds/genre-append.yml` = **既存 genres を消さずに足すだけ**の seed。

## なぜ要ったか

promote のジャンル決定は if/else の**排他分岐**で、どの枝も `new_yml["genres"] = ...` と**代入**する:

| 既存seed | 挙動 | 問題 |
|---|---|---|
| `genre-additions.yml` / `genre-wiki.yml` | trusted に union → `genres = trusted のみ` | 既存 provisional が**消える** |
| `genre-rakuten.yml` | `genres` を置換 + `genres_rakuten: true` + provisional 除去 | 既存分まで「高精度」と**詐称** |
| `genre-enrich-2425.json` | 置換 | 同じ |

= 「provisional を保ったまま1ジャンルだけ足す」経路が**無かった**。

## 仕様

- `_promote-bulk-v2.py` の `_load_genre_append()` / `_GENRE_APPEND`。ジャンル決定の**直後**に union。
- ★**フラグ(`genres_provisional` / `genres_rakuten`)を一切変えない** = 出所と信頼度を詐称しない。
- ファイル不在なら空dict = **挙動完全不変**(検証済: 対照3頁がバイト単位で一致)。
- master32 検証 + baseball/soccer→sports 併記は他経路と同じ。
- ★trusted 作を載せれば trusted にも足さる。**載せない方針は生成スクリプト側で担保**
  (`_genre-rakuten-branch-apply.py` は `genres_provisional`/空 のみを候補にする)。手編集時は効かない。

## 初回の中身

楽天 `booksGenreId` の**主題枝**由来の romance 178作。

- ★コミック直下(001001…)は**出版社×レーベル/判型**の分類で主題を持たない
  (300件以上の76枝のうち**71枝が単一出版社80%以上**)。ここからジャンルは取れない。
- ★別枝に主題性がある: **001029002(TL)→romance P=100%** / **001021002(BL)→romance P=90%**。
- ★**bl は P=64% で不採用**。BL語彙(ノンケ/オメガバース/発情期/アルファ)を掛けても**64%でリフト無し**。
  ただし外れた作を読むと明らかにBL = **truth-gap型**(AniList/Wiki側に bl キーが無いだけ)。
  救済するなら本文での2パス検証(463作)。isekai/gourmet が96%confirmだった前例と同型。
- level-3(001001001/002/003/004)= 少年/少女/青年/レディース は **demographic** として既に利用中。

## ★不達2型を恒久修正 (= 2026-08-03。ラブコメ2,939件適用で発覚・commit a42b56d11)

seed を書いても**永久に届かない**頁が2型あった。どちらも「本流の適用点(ジャンル決定の直後)に
来ないか、来ても引くキーが違う」型:

1. **slug-override頁**(`slug-overrides.yml` 経由・実測**1,037件**)= 適用点の `slug` は
   `_slug_override()` を通す**前**のSRC slug。seed は本番索引の**公開slug**で書くので永久に不一致。
   → `{slug, new_yml["slug"]}` の**両方**で引くよう修正。
2. **予約頁**(`data/seeds/preorder-pages/*.yml`)= 種2を通らない別ストリームで、
   catch/synopsis/publisher/書影の seed だけ通していて **genre-append は素通り**だった。
   → 予約ストリームにも同じ union を追加(既存genres不変・フラグ不変)。

★教訓= **seed の適用点は1箇所とは限らない**。予約頁ストリームは「種2を通らない」ので、
新しい seed を結線する時は**本流+予約ストリームの2箇所**を必ず見る。

## ★踏んだ罠(繰り返さない)

**manga.v2 への直接パッチは promote を通すと消える**。178作を直接パッチ→そのまま
`_reflect-targeted.py`(中で `promote --only`)を走らせて**全件巻き戻した**。
方法D(`_genre_rakuten_apply_inplace.py`)は「promoteを通さない」前提の手法。
→ 恒久化したいなら**必ず seed 化**する。これがこの仕組みを作った直接の動機。

関連: [[genre_from_rakuten_story_plan]] [[ai_genre_closed_vocabulary]] [[genre_quality_improvement]]
