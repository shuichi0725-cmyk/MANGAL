---
name: year_suffix_slug_survey
description: "【調査済・未着手】年サフィックスslug(-西暦)全1,976頁の分裂洗い出し。ISBN交差=確定4件/同題要判定106/版割れ多数。worklist=docs/production-diagnostics/year-suffix-all.tsv"
metadata: 
  node_type: memory
  type: project
  originSessionId: 164c5cf9-b3fb-40f8-a19c-7cc4f6403843
  modified: 2026-08-07T00:50:52.893Z
---

2026-08-07 ユーザ指示「jin-2011のように-西暦は分裂の可能性が高い。全件洗い出して調査して」の結果。
**調査のみ・是正は未着手**(ユーザ「調査結果だけ残しておいて」)。

## ★まず jin-2011 は分裂ではなかった
ファイル名 `jin-2011` だが **公開slugは `jin`**(slug-overrides.yml で2026-06-16に無印化済)。
同じ「ファイル名は年付き・公開slugは年なし」が **41件**。
★**ファイル名で数えると誤る**([[edition_overrides_key_is_public_slug]]と同じ罠)。内部 `slug:` で数えること。
`.cache/prod-slug-map.tsv`(file→slug→title)を作る1パスが早い。全68,782頁中 ファイル名≠内部slug は **1,035件**。

## 全件の内訳(公開slugベース・年付き1,976頁)
| 分類 | 件数 | 中身 |
|---|---|---|
| A 題に年が入っている | 68 | 正当(AKIRA 2019型) |
| B 基底slugも実在 | 1,148 | 衝突解決の年サフィックス |
| C 基底slugが無い | 760 | 衝突相手が消えた/改名済。年だけ残骸として残っている |

## 分裂判定(著者交差218ペアのISBN交差)
worklist = **`docs/production-diagnostics/year-suffix-all.tsv`**(判定/分類/巻数/ISBN交差/題/著者/公開slug)

- **ISBN交差あり=確定4件**
  - `shiori-experience-2021`(22巻)⇔`shiori-experience`(15巻) 交差14 = **題の表記揺れによる真の二重頁→統合**
  - `kusuriya-no-hitorigoto-shino-2017`(18)⇔`kusuriya-no-hitorigoto`(24) 交差7 = ねこクラゲ版/しの版は**別作品**→混入巻除去
  - `uchuu-senkan-yamato-2005`(3)⇔`uchuu-senkan-yamato`(9) 交差3 = 完結編/本編は別物→混入巻除去
  - `hidarikiki-no-eren-nifuni-2020`(7)⇔`hidarikiki-no-eren`(26) 交差2 = 原作版/リメイク版は別物→混入巻除去
  ★後ろ3件は**統合してはいけない**(別作品どうしの巻の滲み)。
- **同題・ISBN無交差=106件**(要判定)。★目立つ型= **同一作品の版が別頁に割れている**
  (エスパー魔美が3頁 `esper-mami`/`esper-mami-1996`/`esper-mami-1996-2`、水滸伝3頁、剣客商売・宮本武蔵・武田信玄…)。
  鬼平でやった版タブ統合と同型だが、版の実体を1件ずつ確認しないと確定できない。
- 別題・ISBN無交差=90件 = 概ね正当。

## 既存監査との関係
`scripts/_audit-year-suffix-dup.py` は「基底slugが実在する同著者ペア」しか見ない(今回実行=69組)。
**基底slugが無いC類760件を構造的に取りこぼす**。今回の洗い出しはそこを埋めたもの。

## 残タスク(ユーザ判断待ち)
1. 確定4件(SHIORI=統合 / 残り3件=混入巻除去)
2. 106件を巻数順に per-case 版統合
3. C類760件の無印化(URL整形・表示不変)

関連: [[year_suffix_dup]] [[slug_collision_year_rule]] [[edition_canonical_mechanism]]
