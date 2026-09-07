---
name: slug_rename_kills_slugkeyed_seed
description: 【型・封鎖済】公開slugをキーにするseed(isbn-fill/edition-overrides/status-corrections)は、slug改名で無警告に効かなくなる。promoteのloaderで旧キーも引くようにした
metadata:
  type: project
---

2026-09-07。 週次前のISBN消失消し込みで発覚した**構造バグ**。

## 何が起きるか
promote は `o["slug"] = _slug_override(src_yml["slug"])` = **改名後の公開slug**で seed を引く。
seed 側のキーは書いた当時の公開slug(=改名前)のままなので、
`slug-overrides.yml` で頁を改名した瞬間に **そのseedが無警告で効かなくなる**。
エラーも警告も出ないので、頁が静かに劣化する。

**実害(2026-09-05の改名で発生 → 09-07に発見)**:
`isbn-fill.json` の4頁が外れ、**ISBN 9本が本番から消えた**
(紅い牙 ブルー・ソネット v1,2,3,13 / サンダー大王 v2,3 / 純愛とセックス v2 / ハーレム革命 v2,3)。
種2はこれらの巻を**元からISBN無し**で持っており、ISBNは isbn-fill が補充していた。
掃引すると同じ状態が **edition-overrides 52頁 / status-corrections 32頁**にもあった(計86頁)。

## 見つけ方
`_audit-isbn-loss.py` の「★理由なし」に出る。 頁は生きているのに巻のISBNだけ消えるので
「頁drop」でも「巻の削除」でもなく、原因が見えにくい。
掃引= 各seedのキーを本番索引の公開slug集合と突合し、`slug-overrides.yml` で追えるものを数える。

## 封鎖(実装済)
`scripts/_promote-bulk-v2.py` の `_alias_expand(d)` を3つの loader に噛ませた:
`_load_isbn_fill` / `_load_edition_overrides` / `_load_status_corrections`。
**読み込み時に旧キーを `_slug_override()` 後のキーでも引けるよう複製**する
(新キーが既に在れば新キー優先=上書きしない)。 ★seed 自体は書き換えない = 来歴が消えない。

## 併発して露出する型
死んでいた override が復活すると、**override 自体が古くて後の巻を含んでいない**ことがある
(overrideは editions を丸ごと置換するため巻が減る)。 2026-09-07 は2件:
恋ヶ窪くん v10 / 新編集パーマン v9のISBN。 復活させた後は必ず ISBN消失監査を再実行する。

## 教訓
★**公開slugをキーにするseedを作ったら、改名との相性を最初に考える**。
SRC stem をキーにする seed(edition-canonical)はこの問題が起きない。
[[edition_overrides_key_is_public_slug]] [[edition_canonical_key_is_src_slug]]
[[pubslug_src_stem_generator_trap]] [[slug_override_deadform_flat]]
[[weekly_isbn_loss_acknowledge_flow]] [[feedback_one_bug_means_a_class]]
