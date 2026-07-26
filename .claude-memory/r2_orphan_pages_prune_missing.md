---
name: r2_orphan_pages_prune_missing
description: "本番R2に孤児HTML 1,041頁(ローカルでdrop済なのに公開され続けている)。r2-syncは--prune無しが既定"
metadata: 
  node_type: memory
  type: project
  originSessionId: dff8a305-89f9-41d1-baa4-d9b9d0478784
  modified: 2026-07-26T11:31:37.967Z
---

★**本番サイトから消したはずの頁が消えていない**(2026-07-26 発見)。

## 事実
- `scripts/_r2-sync.py` は **`--prune` を付けた時だけ**「ローカルに無いキー」をR2から削除する。
- ★**週次蒸留 skill の実行行は `python scripts/_r2-sync.py --bucket mangal-site`** = **prune無し**。
  → drop した頁の HTML は R2 に残り、URLは200のまま生き続ける。
- 実測(2026-07-26): `.cache/r2-manifest.json`(137,695キー)と `data/manga.v2` を突合し
  **孤児HTML 1,041頁**。 この日のフィルムコミック掃引で落とした45頁のうち**35頁が公開中**。

## 効く場面
- 非掲載判定(非漫画/フィルムコミック/重複)を下しても**サイト上は残る**ので、監査の「本番から消えた」は
  data/manga.v2 の話であって公開状態ではない。 [[feedback_production_deploy_gate]]
- Googleにインデックス済みのURLが残るため、消したい頁ほど残る。

## ★対処済み(2026-07-26 ユーザ指示で週次に組込)
- `_r2-sync.py` に安全弁を実装: **`--prune-floor 0.9`**(out/のmanga頁が前回の90%未満なら削除中止=
  build途中失敗の全消し防止) / **`--prune-max 3000`**(超過なら削除せず報告) / 削除キーを
  `.cache/r2-pruned-<日時>.txt` へ実行前に記録。 判定は `--dry` でも表示される。
- **weekly-distill skill の実行行を `--prune` 付きに変更**。
- ★**初回の週次で約2,100キー(孤児1,041頁×html+txt)が削除される**見込み = 正常。
  中止された時はログを確認し `--prune-max <件数+100>` で再実行する。
