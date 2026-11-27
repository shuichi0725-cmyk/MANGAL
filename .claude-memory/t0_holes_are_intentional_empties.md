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

## 2026-11-27 適用済み(ユーザ「作る」「お願い」)
- ★対応表 = `data/seeds/imprint-demographic.yml`(54レーベル+レーベル欄なしのlibre)。裁定: **BL・女性向け(恋愛/TL/女性向け異世界)=josei** / 男性向け異世界=shounen(既存多数派) / 少女 / 青年。混在レーベル(KCデラックス/MFC/コロナ等49)は載せない。
- promote `_fill_demographic_from_imprint` = 本流の最終pass + **予約頁経路(preorder-pages)の両方**(予約頁は本流を通らない穴の11件目)。空の頁だけ・版ごとに値が割れたら埋めない。今後の新頁にも自動で効く。
- 結果: demographic 空 1,725 → **987**(738頁反映・a29358580d)。
- ✅ ユーザ裁定「b」: 女性向けレーベルなのに shoujo 258 / shounen 50 の **308頁を josei に揃えた**(seed `realign:` = ここに在る頁だけ既存値を上書き・changelog imprint-demographic-changelog.jsonl)。テスト環境に計1,044頁投入。
- ⏳残り: 男性向け異世界なのに seinen 99・少女レーベルなのに josei 31 等は未裁定のまま / promote の既定値 `src_yml.get("demographic","shounen")`(不明を少年で埋める)を空にするかは未裁定。
- ついでに発見: `data/manga.v2/` に 6/18 の `*.yml.offbak` が1,189個残っている(`_offset_harvest.py` の退避)。未処理。

- 2026-11-27 追: 少女レーベル(プリンセス・コミックス/講談社コミックス別冊フレンド)なのに josei だった30頁を realign で shoujo に揃えた(ユーザ「なおして」)。realign計338(josei308/shoujo30)。残る未裁定=男性向け異世界レーベルでseinenの99頁・promoteのshounen既定。
- 2026-11-27 追2: ユーザ「男性向けは青年でよい。成年は使いたくない」→ 表の男性向け異世界6レーベルを shounen→seinen。空欄充填分99頁が seinen に。元データで shounen の211頁は未変更(揃えるか裁定待ち)。
