---
name: genre_derive_rules_layer
description: "【✅】派生ジャンル規則=promote恒久層(_genre_rules.py)。枯れキー(romcom/gag/war/yokai/4-koma)が新規作品でも自動給水。バックフィル2,301頁適用済"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-03T01:38:22.153Z
---

★**「注ぎ手がいない枯れキーは自動で増えない」構造を恒久修正**(2026-08-03 ユーザ裁定
「自動で増えない構造を改善したい。今後は自動で増やせないか」)。

## 仕組み

- **正本= `scripts/_genre_rules.py`**(共有モジュール)。promote(`_promote-bulk-v2.py`)の
  **本流+予約ストリーム両方**が全頁で毎回呼ぶ = 蒸留で入る新規作品にも自動で付く。
- 導出元(明記主義・fail-closed): ①タグ名(★AniList**英語原名**のまま格納=Youkai/War/Military/
  Mahou Shoujo/Samurai/4-koma。和名は楽天/AI由来) ②題名(4コマ) ③紹介文(catch+synopsis:
  ラブコメ/ギャグ/4コマ/妖怪)。union only・フラグ不変(genre-appendと同じ流儀)。
- **ガード**(2026-08-03 目視検品で確定):
  - タグは **rank≥60**(AI生成タグrank55を弾く)
  - war/時代劇/魔法少女は**タグのみ**(紹介文は「受験戦争」「時代劇が大好きなJK」(クロエの流儀)、
    「魔法少女ものから…の短編集」(歌姫Fight!)型で誤爆)
  - 4コマ紹介文は「巻末/おまけ/併録/収録」含みを除外(おまけ4コマ型)
- samurai/mahou-shoujo は既存の信頼マッピングで既に付いており規則からの新規0=正常。

## バックフィル(2026-08-03 適用済)

- `python scripts/_genre_rules.py --list` → `docs/production-diagnostics/genre-rules-backfill.tsv`
  (stem/出所/追加キー/根拠つき=人が検品できる形)
- 実績: **2,301頁**(romcom+561 / gag+519 / war+439 / yokai+428 / 4-koma+423)を
  700件チャンク×4のtargeted反映で本番manga.v2+索引へ適用。
- 月次サニティ観点: キー別件数の急変は規則の誤爆signal(TSVを再生成して差分を見る)。

## 関連

- romcom本体のバックフィル(romance∩comedy 7,184作のAI裁定)= [[romcom_backfill_state]](適用済)。
  規則層はその「明記層」を恒久自動化したもの。判定が要る非明記層は skill romcom-judge が続き。
- [[genre_append_seed_mechanism]] [[ai_genre_closed_vocabulary]]
