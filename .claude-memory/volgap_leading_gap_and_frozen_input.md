---
name: volgap_leading_gap_and_frozen_input
description: 【是正済】巻抜け検出の穴2つ=①minとmaxの間しか見ず「1巻が無い」を見逃す ②入力のvol_gap.tsvが2026-07-16で凍結し誰も再生成していなかった
metadata:
  node_type: memory
  type: project
---

2026-09-06 ユーザ発見(『皆様の玩具です』= standard 4..9 で 1,2,3 が無いのにデバッグの巻抜けに出ない)。
**穴は2つ**あって、どちらも直した。

## ① 判定が「minとmaxの間の穴」しか見ていなかった

索引(`_build-list-index.py`)も監査(`_volgap-virtual.py`)も同じ式:
`ns[-1]-ns[0]+1 > len(ns)`。 4..9 は連続なので穴ゼロ = **先頭がごっそり欠けた頁は素通り**。
`solo_nonfirst` は `tv==1`(単巻)限定なので複数巻の先頭欠けも拾わない。

★**判定は「頁全体の最小巻>1」で見る**(版単位にすると偽陽性を巻き込む)。 本番実測:
- 先頭欠けの版 563件 = ★**頁全体に1巻が無い 275頁**(本当の巻抜け) + その版だけ途中から 288版
- 後者は 新装版107 / 文庫41 / deluxe34 等で、**他の版が1巻を持っている**= 途中巻からの刊行という
  正当例が多い → 混ぜない。
- 小数巻(15.5型)は先頭判定に使わない(番外編は1巻の代わりにならない)= int だけで見る。

結果: 本番の巻抜け **256頁 → 505頁**(うち「1巻が無い」274)。

★**3か所を揃える**([[build_input_wiring_three_places]] の同型):
`scripts/_build-list-index.py`(`no_vol1` を計算し `vol_gap` にも立てる。 ★新ビット `fl & 32`) /
`lib/listIndexDecode.ts`(`FL_NO_VOL1 = 32` → `no_vol1`) / `lib/schema.ts`(`no_vol1?: boolean`) /
`scripts/_volgap-virtual.py`(`_no_vol1()`。 gap_detail は `(1巻が無い):[1,2,3]` と出す)。
既存ビットは 1/2/4/8/16 なので 32 が空き。 古いデコーダは未知ビットを無視するので後方互換。

## ② ★入力の `vol_gap.tsv` が凍結していた(こちらの方が悪質)

`docs/production-diagnostics/vol_gap.tsv` は **2026-07-16 で止まっていて、誰も再生成していない**
(grep: 読む script 5本 / 書く script **0本**)。 `_volgap-virtual.py` はこれを候補リストにしていたので、
**当時の1,417頁を再チェックするだけ**= それ以後に生まれた巻抜けは永久に出てこなかった。
→ 候補は毎回 **現在の一覧索引の vol_gap フラグ(fl & 2)** から作る。 `--from-tsv` で旧挙動。
★索引は**公開slug**、`data/manga.v2` のファイル名は**SRC stem**なので
`.cache/prod-page-slugs.json` を逆引きして開く(これを通さないと数頁が黙って落ちる)。

## 教訓
- 「検出器が鳴らない」は **判定式** と **入力の鮮度** の両方を疑う。 追記型/凍結型の台帳を
  入力にしている監査は静かに死ぬ([[diag_log_prune_before_reading]] と同根)。
- 是正後の実走: 候補505頁 → 適用前gap 483 / 適用後 469。
  『皆様の玩具です』は `(1巻が無い):[1, 2, 3]` として出るようになった。

**Why:** 巻抜けはサイトの品質の根幹で、しかもユーザが実際に使っているデバッグ表示。
**How to apply:** 巻抜けを触る時はこの2つの穴を思い出す。 関連:
[[volgap_virtual_tool_trigger]] [[volgap_virtual_false_positives]] [[unlisted_volumes_trinity_type]]
[[pubslug_src_stem_generator_trap]]
