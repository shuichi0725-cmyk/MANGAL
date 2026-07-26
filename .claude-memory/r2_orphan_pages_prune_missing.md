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

## 未決
`--prune` を週次に入れるかはユーザ裁定待ち。 ★prune は「ローカルout/に無いキーを全消し」なので、
**buildが不完全な回に走らせると大量削除になる**。 導入するなら削除件数の上限ガード(例: >2,000で中断)を
付けるのが安全。
