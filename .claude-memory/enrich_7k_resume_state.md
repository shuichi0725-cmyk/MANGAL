---
name: enrich-7k-resume-state
description: "キャッチ/詳細エンリッチの進捗と再開点。2026-07-30に残バッチ0191-0204(342作)を新字数規格で生成・適用・本番反映済。残=full 0205-0217(約320作)/genreのみ0218-0380(4,071作)/短キャッチrequeue(4,343作)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f715f40-d14b-4e9a-806c-fe24cfb6fc30
  modified: 2026-07-29T15:44:26.097Z
---

エンリッチ(キャッチ/詳細/ジャンル)の消化状況。材料バッチは `.cache/enrich-batches/batch-NNNN.json`(380本、2026-07-26生成)。

- **kind='full'**(2巻以上・楽天caption有)= catch+synopsis / **kind='genre'**(1巻)= ジャンルのみ(2026-07-14裁定)。
- **7/27の並列生成は190バッチで停止**(4,750作適用済。ただし平均19字で短く、requeue対象になった)。
- **2026-07-30に 0191-0204(342作)を消化**。新字数規格(キャッチ50-70/詳細80-110)で生成 → 適用 → `_reflect-targeted.py` で本番342頁へ反映+push済(検証ゲートOK)。
  - 生成物は git 追跡: `data/enrich-out-2026-07/batch-0NNN.json`(dict形式 {slug:{catch,synopsis,genres_add}})。
  - 適用器 = ★**`scripts/_apply-enrich-batch.py`**(新設)。字数ゲート(catch48-74/syn78-114)+丸写し8gram+master32検証+本番既済skipの純粋追加。`--requeue` で上書きモード。
  - 書込先 = catch-ja.json / synopsis-slug-ja.json / genre-enrich-2425.json / manga-catch-index.json(全てpromote結線済)。

**残り**
- full 0205-0217 = 13バッチ・約320作(材料あり)
- genreのみ 0218-0380 = 163バッチ・4,071作
- 短キャッチ再生成キュー = `docs/production-diagnostics/catch-short-requeue.txt` 4,343作(requeueモードで上書き)

**実装知見(効率に直結)**
- ★キャッチは体感より**10字ほど短く出る**。「約20字×3節」で書いても実測45-47字に落ちるので、**3節目を意識的に長く**(結局2回の字数patchが要る)。手本=hunter-hunter(64字)。
- 材料ダイジェストは scratchpad の `_digest.py`(バッチ番号を渡すと本番未充足のみ整形出力。既にcatch/syn充足済の頁は自動除外)。
- 非漫画候補は生成せず保留にする(実例: `tokyo-kuukan-1868-1930`=明治大正図誌、`tv-animation-major-characters-handbook-heroes`=公式ガイド)。材料が「発売延期」等で実質無い作(`transnauts`)も空のまま。
- 全量一括WFはセッション枠を食うので不可([[enrich-catch-synopsis]] skill が正本)。Opusインラインで2バッチ(約50作)ずつが実用単位。
