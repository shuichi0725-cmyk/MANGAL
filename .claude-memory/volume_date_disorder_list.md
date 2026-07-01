---
name: volume_date_disorder_list
description: 発売日と巻番号の順番が矛盾する長期連載515件の調査リスト(楽天harvest後に是正)。版混在汚染の検出
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

ゴルゴ13型の長期連載で「巻番号順に並べると発売日が逆行する」汚染を検出(2026-06-27・調査のみ)。ユーザ指示=**変更は楽天harvest完了後**。

## 検出
`scripts/_audit-date-disorder.py`: 索引で総巻数≥10(5,384件)に絞り→standard版を巻番号順ソート→発売日が逆行する箇所をflag。**515件** → `docs/volume-date-disorder.tsv`(逆行幅[年]降順・列=slug/題/巻数/逆行数/逆行幅/該当巻#N(日付)→#M(日付)/疑いISBN)。

## 正体(汚染の型)
旧連載(1970-80s)に**新装版/文庫/復刻の巻が混入し標準版で版が混在**=巻Nが再版日(2010s)・巻N+1が初版日(1970s)で逆行。例: golgo-13(220巻・逆13・#81 2006→#82 1992) / ippei-zenshuu(60年差) / houchounin-ajihei(52年差) / swan / sukeban-deka / 子連れ狼 / harenchi-gakuen。

## 修正方針(harvest後・per-case)
- **再版日混入**: その巻のISBNを初版ISBNに差し替え or 発売日を初版日に正規化。
- **版混在**: standard版から新装版/文庫の巻を分離(別editionタブへ)。
- **真の別作混入**: `volume-exclude.yml`(slug×isbn13)で除去([[fragmentation_overmerge_cleanup]]の機構)。
- ★楽天harvest(rakuten-isbn.jsonl)で各ISBNの正確な初版発売日が揃ってから判定すると精度が上がる。
- 関連: [[multi_edition_unification_pending]](版違い統合)/[[audit_volume_output_detector]]/[[madb_volume_misnumber_fix]]。

## 姉妹: 巻数抜けリスト(同時作成・同じharvest後是正キュー)
`scripts/_audit-volume-gaps.py`→`docs/volume-gaps.tsv`(commit 79c6803b9)。standard版で巻番号1..maxの欠番を検出=総巻数≥3の28,068件中**647件**(うちratio≥0.8&max≥5の取りこぼし濃厚**269件**)。完成度ratio降順=ほぼ揃って数巻欠けが上位。例: mogura-no-uta(92/94欠86,87)/kenkaku-shoubai(53/54欠50)/q-e-d(欠vol1)/tough(欠17)/major-2nd(欠29)。修正(harvest後)=欠番ISBNを楽天/NDLで取得し**種4(volumes-supplement.yml)**で補完。
