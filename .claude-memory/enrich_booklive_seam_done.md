---
name: enrich_booklive_seam_done
description: "【✅完走】BookLive紹介文=エンリッチ第2材料源。初回harvest 1,086件のうち使えた1,029件+楽天43件=1,071作を2026-08-27に全消化。次はharvest増加分だけ"
metadata: 
  node_type: memory
  type: project
  originSessionId: 79cc8af0-e2f8-4bd2-b6af-b897f077da5c
  modified: 2026-08-27T07:37:19.370Z
---

楽天captionが枯れた層([[enrich_newest_seam_exhausted]])に対する**第2材料源=BookLive商品頁の1巻紹介文**の初回運用が完走した。

## 何をしたか (2026-08-27)
- 材料 = `.cache/booklive-desc.jsonl`(1,086件。`_booklive-desc-harvest.py` の初回収穫)。**60字未満57件を除く1,029件**が使えた。
- これに楽天caption側の新規42件(本番化した予約頁=2026-10〜11発売の2巻以上)を足し、**1,071作**を22バッチ(batch-9301〜9322)で消化。
- 結果: **catch+1,069 / syn+1,068 / genre+11 / 上書き0**。本番反映(promote 1,070頁+索引)まで完了。

## 恒久化した道具
- ★`scripts/_enrich-booklive-stage.py` = booklive-desc.jsonl(+楽天materials.jsonl)を applier が読む材料バッチ形式へ落とす。
  `--start 9301 --size 50`。**BookLive descも caption として入れる**(applierの丸写し8gram検査が効くため)。
  本番頁で catch/syn 両方済みの頁は自動除外するので、**次回は増加分だけが staged される**。
- ★`scripts/_enrich-digest.py` = 材料バッチを人間可読ダイジェストへ(**UTF-8ファイル出力**)。
  ★Windowsコンソールはpython printが cp932 で化けて材料が読めない。`cat` できるファイルに落とすのが正解。

## 次にやる人へ
- BookLive層は**試し読みharvestがアンカーを増やすたびに対象が広がる**。増えたら `_booklive-desc-harvest.py` → `_enrich-booklive-stage.py --start 93NN` で同じ流れ。
- ★**大きな生成ファイルはBashヒードキュメントで書けない**(10KB級で `unexpected EOF` になる)。Writeツールでbase(`bNNNN.py`)を書き、字数是正だけ小さなヒードキュメントで `bNNNNfix.py` に足す運用が安定。
- ★字数は**catchが必ず46-47字で止まる**(下限48)。3文構成にしても足りず、毎バッチ是正パスが1回要る。最初から各文を長めに書くこと。

## 未達1件 (= 既知の型)
`shikakenin-fujieda-baian-saitou2002`(仕掛人藤枝梅安)だけ本番頁に載らなかった。
公開されているのは**源なしの orphan 頁** `shikakenin-fujieda-baian-saitou.yml` で、SRC側(...2002)はpromoteがdropするため
seedが永久に届かない = [[orphan_source_pages_restored]] の型。seedキーは両方入れてあるので、頁の重複が解消されれば載る。

関連: [[enrich_newest_seam_exhausted]] [[enrich_7k_resume_state]] [[catch_synopsis_enrich_pending]]
