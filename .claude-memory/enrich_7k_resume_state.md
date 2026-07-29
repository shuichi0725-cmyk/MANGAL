---
name: enrich-7k-resume-state
description: "キャッチ/詳細エンリッチの進捗と再開点。2026-07-30に0191-0217(645作)を新字数規格で消化・本番反映済。★full系バッチは全消化=残は genreのみ0218-0380(4,071作)と短キャッチrequeue(4,343作)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f715f40-d14b-4e9a-806c-fe24cfb6fc30
  modified: 2026-07-29T16:40:50.569Z
---

エンリッチ(キャッチ/詳細/ジャンル)の消化状況。材料バッチは `.cache/enrich-batches/batch-NNNN.json`(380本、2026-07-26生成)。

- **kind='full'**(2巻以上・楽天caption有)= catch+synopsis / **kind='genre'**(1巻)= ジャンルのみ(2026-07-14裁定)。
- **7/27の並列生成は190バッチで停止**(4,750作適用済。ただし平均19字で短く、requeue対象)。
- **2026-07-30に 0191-0204(342作) + 0205-0217(303作) = 645作を消化**。新字数規格(キャッチ50-70/詳細80-110)で生成→適用→`_reflect-targeted.py`で本番反映+push済(検証ゲートOK)。
  - 生成物は git 追跡: `data/enrich-out-2026-07/batch-0NNN.json`(dict形式 {slug:{catch,synopsis,genres_add}})。
  - 適用器 = ★**`scripts/_apply-enrich-batch.py`**。字数ゲート(catch48-74/syn78-114)+丸写し8gram+master32検証+本番既済skipの純粋追加。`--requeue` で上書きモード。
  - 書込先 = catch-ja.json / synopsis-slug-ja.json / genre-enrich-2425.json / manga-catch-index.json(全てpromote結線済)。

**残り**
- ★**full系は 0217 で打ち止め**(0205-0217が最後の13バッチ)。
- genreのみ 0218-0380 = 163バッチ・4,071作
- 短キャッチ再生成キュー = `docs/production-diagnostics/catch-short-requeue.txt` 4,343作(requeueモードで上書き)

**実装知見(効率に直結)**
- ★キャッチは体感より**10字ほど短く出る**。48字ゲートに1字足りない「47字」落ちが頻発するので、**最初から60字強を狙う**(3節目を長く)。手本=hunter-hunter(64字)。
- 材料ダイジェストは scratchpad の `_digest.py`(バッチ番号を渡すと本番未充足のみ整形出力。充足済頁は自動除外)。`CAPLEN=260` 環境変数でcaption切詰め長を調整=読む量を圧縮できる。
- ★**2026-07-30 修正**: `_apply-enrich-batch.py` の master32 ローダが `genres.yml`(=key直下の平坦dict)を `.get('genres')` で読んでおり**ジャンル検証が常に失敗**していた(genre付与が全て弾かれる)。dict分岐を追加して修正済。
- 保留にする型: 傑作集/編集本(ワタシの川原泉)・材料が実質空(ヤバ盛/吉野家兄弟)・評伝など非漫画候補(闇の王子ディズニー)・**フィルムコミック**(ズートピア=掲載境界)。捏造せず空のまま残す。
- 全量一括WFはセッション枠を食うので不可([[enrich-catch-synopsis]] skill が正本)。Opusインラインで2バッチ(約50作)ずつが実用単位。
