---
name: hidden_editions_pending
description: 【保留・ユーザ指示 2026-09-07「今度にする」】種2にISBN付きで在るのに本番に1冊も出ていない版の是正。着手は必ずレーベル分類から
metadata:
  type: project
---

2026-09-07 ユーザ「今度にする。覚えておいて」。**着手前にこの記憶を読むこと。**

## 何の話か
promote は版タブを **type だけ**で束ねる(`group_key = effective_type`)。 そのため同じ type の
別レーベルが1タブに合流し、**巻番号の衝突で負けた版が丸ごと本番に出ない**。
番号は埋まるので「巻抜け」にも見えず、気づけない。

発端 = 『夕陽よ昇れ!!』(あだち充)。 フラワーコミックスワイド版(1992・9784091338938)が種2に在るのに
通常版(1980)と番号1が衝突して不可視だった。 ISBN消失監査の「★理由なし」で初めて表面化した。
→ canonical seed の `extra_editions` に `type: wideban` で追加して是正済(**これが型見本**)。

## なぜ既存検出器に載らないか
`_audit-edition-typemerge-loss.py` は **ISBNから引いた出版社が実際に違う**時だけ挙げる設計
(imprint文字列比較は「あすかコミックス / ASUKA COMICS」型の表記ゆれを誤検出するため)。
夕陽よ昇れ!! は**同じ小学館の別レーベル**なので意図的に対象外。 → [[edition_typemerge_hides_volumes]]

## 再算出(いつでも打てる)
```
python scripts/_scan-hidden-editions.py    # → docs/production-diagnostics/hidden-editions.tsv
```
2026-09-07 実測 = **4,620版 / 16,405巻**。 promote の除外レーベル語を当てた残り **3,909版 / 11,264巻**。

## ★★着手の第一歩は「レーベル分類」(件数をそのまま仕事にしない)
残り3,909にも**コンビニ廉価再録が相当混じっている**。 実際のレーベル上位は
`Akita top comics wide` 100 / `KCDX` 81 / `My first wide` 49 / `SP pocket wide` 49 /
`BEAM COMIX` 48 / `KCスペシャル` 38 / `Goma books` 37 / `ジャンプコミックスセレクション` 36 /
`HMB` 33 / `あすかコミックスDX` 31 / `ACTION COMICS` 31 / imprint空 465。
= 「正規の別版(ワイド版/新装版/デラックス)」と「廉価再録(コンビニ/セレクション)」が同居している。
**先にレーベルを2分し、正規の別版だけを worklist にする**。 [[feedback_raw_count_is_not_worklist]]

## 是正の型
per-case で **edition-canonical seed の `extra_editions` に版タブとして足す**
(夕陽よ昇れ!! / 隻眼の竜が型見本)。 ★共有ロジックは触らない:
- `group_key` を (type×imprint) にすると ARMS型の表記ゆれを誤って割る [[imprint_split_arms_type]]
- `separate_editions`(series-merge.yml) は sid単位なので1sidが複数版を持つ形に効かない

## ついでの所見(実害なし)
除外レーベル語に「マイファーストビッグ」(カナ)と `REKC` が無い(英字 "My first big" のみ)。
ただし**本番表示は0版**なので急ぎではない。 直すなら `DROP_IMPRINT_PATTERNS` に追加。

[[edition_typemerge_hides_volumes]] [[edition_canonical_mechanism]] [[weekly_isbn_loss_acknowledge_flow]]
