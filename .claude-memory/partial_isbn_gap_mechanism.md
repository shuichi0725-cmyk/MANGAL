---
name: partial-isbn-gap-mechanism
description: がきデカ型=一部ISBN欠け巻の機械是正(2026-08-19適用済669巻)。isbn-fillキー=公開slug罠も
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-19T13:33:03.932Z
---

# がきデカ型 = 一部ISBN欠け巻(→書影なし)の是正 (2026-08-19 適用済)

発端 = がきデカ(SCC v1-4のISBN欠け=書影なし。Wiki×楽天で確定、v5と帯連番整合)。

## 機構 = `scripts/_fix-partial-isbn-gaps.py` (dry-run既定 / --apply)
- 対象 = 同一edition内でISBN有巻/無巻が混在(初回824頁/2,179巻)
- 候補2経路: ①帯内挿/外挿(コード=定数+巻番号の線形連番) ②楽天キャッシュ逆引き((正規化題,巻)→ISBN、一意のみ)
- **4検証すべて通過のみ自動適用**: 楽天題に頁題含む+巻番号一致 / 出版者帯(先頭8桁)がedition多数派と一致 / 本番未使用 / 楽天にレコード実在
- 適用先 = isbn-fill.json(空巻のみ充填=promoteガード)。書影はcovers seedから自動付着

## 実績: 289頁669巻確定(内挿171/外挿136/逆引き362)、書影193巻復活
- **canonical結線頁560巻は自動不可**(canonicalが後勝ちでfill無効→canonical本体へ書く。がきデカ自身がこれで、per-case時にisbn-fillが不着→canonical直書きで解決)
- 未解決945巻 = `docs/production-diagnostics/partial-isbn-gap-unresolved.tsv`(多くはISBN制度(1981)以前の古書=真に無ISBN)

## ★罠: isbn-fill.json のキー=公開slug (edition-overridesと同じ)
SRC stemは死にキー=無警告不適用。slug-override頁11件が不着→公開slugへrekeyで解決(実踏)。
[[edition-overrides-key-is-public-slug]] と同族。edition-canonicalだけがSRC slugキーで逆。

書影なしの正当ケース: 楽天noimage(双葉社がきデカ/豪華版)=アフィ元画像のみ原則で書影なしが正。
