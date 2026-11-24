---
name: ndl-dump-uses
description: NDL全件データ(OAI-PMH 2026-11-07版・D:\NDL 元26,408本/抜き出し .cache/ndl-dump/all.jsonl.gz 326k件)の使い道と 2026-11-25 の実施結果
metadata:
  type: project
---
NDL 全件ダウンロード(`scripts/_ndl-dump-extract.py`)= opensearch の 429 と無関係に NDL 書誌を引ける。抜き出し条件=サイトISBN一致 or NDC726.1/Y84。統合版 `.cache/ndl-dump/all.jsonl.gz`(isbn/title+kana/volume/series/creators(名前・ヨミ・典拠ID)/dc_creator(役割つき)/date(年月)/edition/ndc…)。

2026-11-25 ユーザ「1、3、4、7はやってほしい」の結果:
- #7 発売日: 日付なし/年だけは全体で409冊しかない → NDL年月で119冊。★promote の最終passに release-date-supplement を通した(源頁・種4経由の頁に届いていなかった)。NDL の date は年月まで(日は無い)。
- #3 著者: author-yomi.yml に典拠ヨミ 2,327名追加・743名是正(値が名前そのまま=ひらがな/漢字)→6,892頁反映。著者頁URLが変わったのは3名だけ。★報告のみ: 食い違い53名(背筋=セスジ等 NDL が正しい例あり)・同名で典拠ID複数14組(.cache/ndl-yomi-plan.json / ndl-author-check.json)。NDL ヨミは ヅ→ズ・ヲ→オ の表記規則なので既存カタカナとの差は書かない。
- #4 版: NDL叢書名が同じ・巻相補で連番の割れ19頁を1版に(canonical新設9・既存canonical内の統合10)。★版表示で「特装/限定」なのに通常版の位置にある巻214冊 → 通常版を NDL(31)+楽天(152・題+巻で1件・発売日±7日)で特定し special-edition-fix へ計182冊。残り49冊は楽天で通常版が1件に絞れず(.cache/special-ng-rakuten.json)。
- #1 巻抜け: 残194頁の欠番は ISBN の無い古い本ばかりで NDL ダンプでは埋まらない(確実一致2冊も著者不明の選集で見送り)。
- 次の候補: #2 取りこぼし(漫画分類だが頁に無いISBN)/ 著者役割の見直し928 / 短編集の収録作 / 漫画でない頁(NDC≠726.1)。★商用利用は NDL への申請が要る可能性あり(未確認)。
関連: [[distill_2026_11_1222]] [[feedback_no_d_drive]]
