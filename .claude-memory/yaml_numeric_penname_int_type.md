---
name: yaml-numeric-penname-int-type
description: 【型・封鎖済】数字だけのペンネーム(359=サコク)がYAMLの引用漏れでintになり、著者名をjoinする生成器が週次の途中で落ちる
metadata:
  type: project
---

**症状**: 週次手順1の `corner-auto` が `TypeError: sequence item 0: expected str instance, int found` で abort。
実体 = 『とうがらしドラゴンのシン』の著者が**数字だけのペンネーム「359」**(ヨミ=サコク。3=サ/5=コ/9=ク の語呂)で、
`data/seeds/source-pages/*.yml` に `- name: 359` と**引用符なし**で書かれ YAML が int として読んでいた。
データは正しく、**引用漏れだけ**が原因(2026-09-22 週次で実踏)。

**掃引**: `data/manga.v2` 69,465頁 + source-pages 全件を型で走査して**1件のみ**。単発だが再発しうる型。

**封鎖**:
1. seed を `- name: '359'` に引用(promoteは str を必ずクォートして書き出すので以後は保たれる)。
2. 著者名を join する生成器3本に `str()` を入れた =
   `scripts/_gen-corner-auto.py` / `_build-sansedai-worklist.py` / `_audit-numeral-variant-split.py`
   (`_gen-review-sheet.py` は元から str())。**週次全体が1頁の型ゆれで止まらない**ようにするのが目的。

**教訓**: 機械追記seedのクォートは「`: ` を含む値」だけの問題ではない([[seed_yaml_colon_quoting]])。
**数字・true/false・null に見える文字列**も同じ穴。新しい書き手を足す時は文字列フィールドを
`isinstance(v, str)` で走査する掃引を一度回す。

★未決(ユーザ裁定待ち): この著者の表記が割れている。楽天=「3:59」/ NDL単話版=「3:59」/ NDL紙版=「359」。
現在は公開中の **359** を維持している。
