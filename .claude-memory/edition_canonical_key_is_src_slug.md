---
name: edition_canonical_key_is_src_slug
description: 【厳守】edition-canonical のキーは SRC slug。edition-overrides(=公開slug)と逆なので取り違えると無警告で効かない
metadata:
  type: project
---

2026-08-08 JIN-仁- の版再構築で実踏。

## 二つの機構でキーが逆
| seed | 参照している変数 | キー |
|---|---|---|
| `edition-overrides.json` | `o["slug"]` | ★**公開slug**(例 `jin`) |
| `edition-canonical/*.yml` | `slug = src["slug"]` (promote L3256) | ★**SRC slug**(例 `jin-2011`) |

slug-overrides で公開slugを付け替えた頁では**両者が食い違う**。
JINでは canonical を `slug: jin` で作ったため**一切適用されず、エラーも警告も出なかった**
(edition-overrides の題修正だけが効いて「一部だけ直った」ように見え、原因を見誤りやすい)。

★**確認法**= reflect-targeted のログに
`★注意: <SRC slug> は edition-canonical 結線slug` が出れば結線できている。出なければキーが違う。
ファイル名は任意(loaderは中身の `slug:` でキーする)が、**SRC slug と同名にしておくと事故らない**。

## 併せて直した promote の穴
`apply_edition_canonical` の `extra_editions` は imprint に **label を代用**していたため、
版タブ名(「文庫版(集英社文庫コミック版)」)がそのまま奥付レーベルとして出ていた。
seed に `imprint:` があればそれを優先するよう修正済(無ければ従来どおり label)。

関連: [[edition_overrides_key_is_public_slug]] [[edition_canonical_mechanism]] [[year_suffix_slug_survey]]
