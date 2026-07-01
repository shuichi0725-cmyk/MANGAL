---
name: edition_canonical_mechanism
description: 版混在汚染の恒久是正機構=edition-canonical seed+promote結線。golgo/釣りバカで実装済。Wikipedia確定vol→ISBN→初版日で版再構築
metadata: 
  node_type: memory
  type: project
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

版混在汚染(=db-v2が全版を1つのstandardに潰し、再版ISBNに初版日が乗る)の**恒久是正機構**。golgo/釣りバカで実装・本番結線済(2026-06-28)。

## 背景(汚染の正体)
- 発売日逆行fix(release-date-override)が「再版ISBNに初版日を貼った」→ golgo/釣りバカ等145作汚染。詳細は[[harvest_match_mechanism_applied]]の反省。
- 根因: db-v2のpopulate(classify_edition_from_imprint)が原版/愛蔵版/廉価版を全部"standard"に潰し、dedupが再版ISBNを代表に選ぶ。
- ★MADB/NDL/楽天は**旧巻の日付が再版日**(同ISBN再版時に再カタログ)。**Wikipediaだけが初版第1刷日を持つ**。版分離もWikipediaの版別表が要(MADB brandは表記揺れ10種で不可)。

## 機構
1. **seed** `data/seeds/edition-canonical/<slug>.yml`:
   - `canonical_label`(例 SPコミックス) + `volumes:[{number,isbn13,release_date}]`(Wikipedia確定の原版)
   - `compact_edition:{label,volumes}`(任意・愛蔵版等)
   - `routing:{brand_contains,title_pattern,exclude_*}`(★新刊を正版へ振分けるルール=連載中の維持用)
2. **promote結線**(`_promote-bulk-v2.py`): `get_edition_canonical()`+`apply_edition_canonical(slug,editions)`。
   main loopのvolume_exclude直後で、該当slugのstandard/compact版をseedで再構築・他版(文庫)温存。cover_url=Null→後段`_apply-covers-stage`がISBN充填。
3. **検証**: `--only golgo-13,tsuribaka-nisshi`で本番manga.v2に反映確認。

## 実績
- 釣りバカ: ビッグコミックス118巻(原版ISBN・書影118/118)。汚染=ワイド版ISBNだった。
- golgo: SPコミックス220巻(原版1973-) + SPコミックスコンパクト176巻(愛蔵版・書影172/172楽天紙) + 文庫40(価値低)。
- routingシミュレーション実証: 新刊は brand+題pattern+連番 で正版に自動振分(逆行0)。連載中も汚染再発しない。

## ★★最重要の優先順位gotcha(2026-07-01痛感)
- **promoteは build_yml(=edition-override適用) の後に L2604 `apply_edition_canonical` を実行**=edition-canonical seedがある slug は **edition-override を上書きする**。
- 帰結: **golgo/釣りバカ等 canonical結線済 slug の版/巻/ISBN修正は `data/seeds/edition-canonical/<slug>.yml` を直す**(edition-overrides.json を直しても無効=上書きされる)。debug print(eov_found=True)で「overrideは適用されてるのに出力が古い」現象でハマった。
- golgo修正例: SPコンパクトの v173欠落+短ISBN4件(v45/59/64/85=9桁=978接頭+check桁欠落)を **canonical seedの`compact_edition.volumes`** で是正→177巻連続・書影完備(2026-07-01)。短ISBN復元= '978'+9桁+check13()。

## ★維持運用(重要)
- 連載中作はseedの`volumes`が固定リスト=**新刊で定期再生成要**(routing ruleでMADBから原版巻を再抽出してseed更新)。未更新だと新刊がページから消える(seedが上書きするため)。月次蒸留に組込む。
- 残: golgo vol123/139の2巻=抽出edge(再版日混入)/ 文庫のKobo誤書影([[kobo_cover_wrong_for_old_print]])/ 他143汚染作のうち真の要修正分(多くは健全と判明)。
- 横展開候補: red77-wiki-isbn.tsvの高品質作(王様の仕立て屋75/75等)。但し多くは「override が既に正しい」ので不要(=ゴルゴ/釣りバカ型の再版代表のみ要)。
