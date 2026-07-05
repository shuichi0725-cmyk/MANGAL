---
name: band-intruder-fix
description: 激マン型/帯混入是正=少数ISBN帯×日付逆行の混入巻を検出→NDL正史×楽天照合で真巻にスワップ。月次サニティ級
---

# 激マン型(帯混入)是正 (= トリガー「帯混入直して」「激マン型見て」)

長期連載の中に**少数ISBN帯で日付が後続majority巻より後**の巻が紛れる型(=別版/コンビニ本/別作の混入)を
検出し、NDL正史×楽天照合の二段ゲートで真巻にスワップする。96頁/170巻で実証(2026-07-05・激マン!で発覚)。

## 検出
```
python scripts/_audit-band-intruders.py
```
- 各頁の各editionで majority帯(≥50%) を基準に、**少数帯の巻で「その巻の発売日 > 後続majority巻の発売日」**を混入と判定。
- 出力 `docs/production-diagnostics/band-intruders.tsv`(slug/edition/vol/intruder_isbn)。

## 是正 (= NDL→楽天の二段ゲート。ユーザ裁定=「ISBN有は潰せる。NDL回してから楽天照合が確度・効率」)
1. **NDL harvest**(該当作をtitle+creatorで全件・★ページング必須):
```
python scripts/_band-intruder-ndl-fetch.py       # 初回(200件/req)
```
   ★NDL SRUは1リクエスト最大200件。大物(009/おそ松=数百版)は`startRecord`で全ページ取得しないと原版を取りこぼす([[external_data_access]]のNDLページング)。取りこぼし時はページング版で再harvest。
   ★BibResourceが2断片に割れ、原版のISBNとvol/dateが泣き別れる型あり→結合処理(merge_fragments)必須。
2. **スワップ生成**(NDL全帯∪楽天直接 の候補から、楽天題完全一致+datefit で確定):
```
python scripts/_band-intruder-swap.py            # dry-run
python scripts/_band-intruder-swap.py --apply    # volume-exclude(混入除去)+種4(真巻追加)
```
   - ★帯は**必須にしない**(出版社移籍作=EAT-MAN[メディアワークス→MF]があるため)。ゲート=楽天題base完全一致+年代整合。
   - 混入ISBN→`volume-exclude.yml`(slug単位)、真巻→`volumes-supplement.yml`(種4・db-v2逆引きでseries_key確定)。
3. **反映**: touchedを `_reflect-targeted.py --only ... --push`。
4. **検証**: 反映後に対象頁の帯統一/日付逆行0を数字で確認。通らない残り(候補なし/複数候補/裏取り不可)は `band-intruders-manual.tsv` へ。

## ゲート(fail-closed)
- 楽天題baseが頁題と完全一致するISBNのみ採用(別作混入を防ぐ)。
- 既にどこかで表示中(isbn-page-index)のISBNは候補外=merge案件として別扱い。
- 複数候補/裏取り不可はabortしてworklist(推測でスワップしない [[feedback_accuracy_is_the_goal]])。

## 実測
第1波(帯厳格)9件→ゲート再設計(帯を参考格下げ)第2波67件=計76件スワップ。残103件=ISBN無古典/複数版でworklist。
月次サニティで再走可(新たな混入型のsignal)。
