---
name: self-declared-deluxe-single-edition
description: 【型・是正済】1版しか無いのに「デラックス版」を自称する通常版(BL多数)。実体はレーベル名。promoteで単独版deluxe→standardに降格・787頁適用
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fa3eed2c-bf86-4ffe-b701-6b416a249bdb
  modified: 2026-09-06T06:52:35.391Z
---

★**ユーザ指摘(2026-09-06)「BL関係で、一つしかないのにデラックス版とか自称する通常版がある」**。

- **実測**: 版が1本だけでそれがデラックス系レーベル = **1,317頁**(うちBL 165頁)。
  KCデラックス239 / あすかコミックスCL-DX139 / ジャンプ・コミックスデラックス137 /
  **ビーボーイコミックスデラックス120** / Akita lady's comics DX74 / drap COMICS DX30 …
  うち **type=deluxe の787頁**は版タブが「デラックス版」で、通常版が存在しないのに
  「どこかに通常版がある」と読めてしまっていた。
- **是正**(`_promote-bulk-v2.py`): **版が1本だけで type=deluxe なら standard/「通常版」へ降格**。
  比較対象が無い=何も隠せないので安全。`imprint`(実レーベル名)はそのまま残す。787頁に適用済み。
- ★**コーナーには元から混入していない**(検算済): 愛蔵版コーナーの条件は「通常版比の巻数圧縮」なので、
  通常版が無いこれらの頁は候補に入らない(0件)。特装版コーナーの3件は実在のvariant由来で正当。
  = [[aizouban_corner_compression_rule]] の「版種名でなく巻数で決める」設計がここでも効いた。

## ★同時に踏んだ罠(一般化して守る)
`isbn-fill.json` のキーは **(edition_type, number)**。降格を isbn-fill の**前**に置いたら
キーが外れて **補充済みISBNが13冊消えた**(超こわい学校の怪談4 / スーパーマリオワールド3,4,6 ほか)。
→ **版種(type)を書き換えるpassは、typeをキーにする全seedの後に置く**。
reflect の減少ゲート([[isbn_dup_special_edition_pass]]の検算の型)が検出して止めた。

**Why:** 「デラックス」「愛蔵版」はレーベル名としても使われるので、**名前は版の格を意味しない**。
**How to apply:** 版の格(豪華/通常)を判定する時は名前でなく**構造**(他版の有無・通常版比の巻数)を見る。
type書き換えを足す時は、typeをキーに引くseed(isbn-fill 等)より後段に置く。
[[aizouban_corner_compression_rule]] [[imprint_split_arms_type]]
