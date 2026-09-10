---
name: seed_silently_ineffective_class
description: 【型・総論】seedに書いたのにpromoteが読まない/キーが違う/フィールド非対応で黙って落ちる。エラーも警告も出ない。書く前に「読み手・キー・搬送フィールド」の3点をgrepで確かめる
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 814118b1-fc50-4622-83ea-59182e2023e1
  modified: 2026-09-10T01:19:07.172Z
---

2026-09-10。**1日で3件続けて踏んだ**ので総論として束ねる。個別事例は
[[slug_override_deadform_flat]] [[katakana_dict_dead_entry_trap]] [[slug_rename_kills_slugkeyed_seed]]
[[skill_rule_without_implementation]] にもあり、**この型は繰り返し出る**。

## 共通形

seed に書いた → 反映した → **何も起きない。エラーも警告も出ない。** 原因は必ず次の3つのどれか。

### ① そのファイルを promote が読んでいない
`dup-merge-alias.yml` に `u12-2018: u12` が2026-06-19から入っていたのに頁は割れたまま。
読み手は `_ambig_merge.py` / `_dedup_finder.py` など**統合ツールと検出器だけ**で、
`_promote-bulk-v2.py` は読まない。promote が読む統合seedは **`series-merge.yml`**。
→ 種2に2 sidが残る限り**フルpromoteのたびに割れ直す**状態だった([[rsc_txt_browser_cache_stale_navigation]] と同じ「効かない配管」)。

### ② キーが違う(同題で種2に複数クラスタ)
`author-role-corrections.yml` に原作者を書いたが無反応。
巻のISBNから逆引きすると sid=139862(`name:ちんくるり|…`)が出るのに、
**頁の代表は sid=75142(`name:イセ川ヤスタカ|…`)** だった。
★判別法 = **種2の `series_authors` が頁の `authors` と一致する sid が代表**。
迷ったら両方のキーに置く(代表が入れ替わっても効く)。

### ③ そのフィールドを搬送していない
`edition-canonical` に `variants`(刷違い併存)を書いたが消えた。
`apply_edition_canonical` の `_v()` は **number / asin / isbn13 / cover_url / release_date / volume_label**
しか組み立てず、variants は落ちる。刷タブは `edition-overrides` 経由(promote 2770行)なら通る。

## ★書く前にやること(30秒)

```
grep -rn "<seedファイル名>" scripts/_promote-bulk-v2.py   # ① promoteが読むか
grep -n -A15 "def apply_.*<機構名>" scripts/_promote-bulk-v2.py  # ③ どのフィールドを搬送するか
```
② のキーは `.cache/db-v2.sqlite` の `series` / `series_authors` を引いて**頁の代表sidを確定**してから書く。

## ★書いた後にやること

**反映して、期待した値が出たかを数字で確認する。** 3件とも「書いた=直った」と思い込めた形だった。
出なければ上の①②③を順に潰す。**死んだ設定は残さず撤去する**(次の人が「書いてあるのに効かない」を再調査する)。

関連 [[feedback_absence_needs_verification]] [[shell_props_serialized_to_all_routes]]
