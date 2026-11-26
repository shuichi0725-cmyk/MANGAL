---
name: t0_holes_are_intentional_empties
description: 台帳監査のT0(demographic空1,725・genres空957)は「公開を止める欠け」ではない=7/13裁定で不明は空で出す。機械で埋まらない(2026-11-27実測)
metadata:
  type: project
---
`_intake-manifest-audit.py` は demographic/genres が空の頁を T0(スキーマ床)と数えるが、2026-07-13 ユーザ裁定で「other は出さない・不明は空」= loader も索引ガードも空を許容。**T0 という層名は古い**(本番を止めてはいない)。

2026-11-27 実測(70,228頁): demographic 空 1,725(2020年代が1,663=新しい1〜2巻の頁化分)/genres 空 957/両方 286。genre_other(仮置き)は **0**(既に解消)。
- レーベル多数決(同レーベル10頁以上・9割一致)で demographic が決まるのは **3頁だけ**。KCデラックス/MFC/KCx 等は混在、フロース/ノヴァ/ハーレクイン/GUSH 等は他頁にも demographic が無い。
- genres 空には非漫画の疑い(例 1-noshitsuketokenkou「1・2・3歳のしつけと健康」BABY BOOKS)も混ざる。

**How to apply:** 「機械で一括充填」は不可。進めるなら ①レーベル→対象読者の対応表を上位レーベルだけユーザ裁定で作る ②genres 空はエンリッチ(楽天紹介文)の経路で、非漫画の疑いは掲載範囲として別に拾う。AIで推定して埋めるのは provisional 付きのジャンルだけ([[ai_genre_closed_vocabulary]])。
