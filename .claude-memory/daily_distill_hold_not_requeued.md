---
name: daily_distill_hold_not_requeued
description: 【未決・構造穴】日次蒸留で保留(hold)になったISBNは prev に入るので次回以降の増加分に二度と出ない=triage簿だけが痕跡。2026-09-02時点9件
metadata: 
  node_type: memory
  type: project
  originSessionId: 450de73b-b605-4986-907d-85f528e9a408
  modified: 2026-09-02T11:51:52.825Z
---

2026-09-02 日次蒸留で確認。`_preorder-increment.py` の fresh = latest − prev(ISBN差分)で、`--commit-prev` は
**保留(ドラフト化しなかった)ISBNも含めた full を prev に昇格**する。increment に hold の再投入は無い(grep で hold/triage 参照ゼロ)。
帰結: `preorder-triage.tsv` の `*_hold` 行(著者不明/ヨミ汚染/全巻回収不成立/slug生成不可)は**人が簿を消化しない限り永久に落ちる**。
月次蒸留で種2に入っても promote は元頁駆動なので新規シリーズは頁化されない([[orphan_series_promote_is_srcpage_driven]])。

2026-09-02 時点の保留9件(全て prev 在): みにくい小鳥の婚約(著者=出版社名) / 六歳の王女ですが(ヨミ汚染) /
ex_mid 7件(夜明けをつれてくる犬・腹パン系ダンジョン配信者・二度目の人生・S級ギルド・ハズレ職・侯爵令嬢リディア・不純すら純情=先行巻がキャッシュに無い)。

**Why:** 「保留=後で通す」つもりの行が、機構上は「二度と来ない」になっている。捏造しない方針で hold を増やすほど取りこぼしが溜まる。
**How to apply:** `_preorder-increment.py` に **hold再投入**を焼く: triage の `*_hold` ISBN のうち ISBN索引(`.cache/isbn-page-index.json`)に無い物を
full harvest から拾って fresh に足す(=毎回再分類→材料が揃った日に自然に通る)。ex_mid の「全巻回収不成立」は楽天 live 題検索の fallback を
`_preorder-gen-midfill.py` に足すと大半が通る(先行巻が2026年刊でローカルcacheに無いだけ)。
併せて未着手の小穴: `clean_kana` は題に巻数があっても**空白無しの末尾巻読み**(…デスイチ)を剥がさない(精霊聖女で手直し)。
KANA_VOLNUM レビューは slug 側しか見ないので title_kana に漏れる。[[intake_manifest_ledger_live]]
