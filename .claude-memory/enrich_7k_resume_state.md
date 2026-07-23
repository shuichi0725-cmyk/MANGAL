---
name: enrich-7k-resume-state
description: "キャッチ/詳細7,048作エンリッチの進捗。完了12バッチ(1,166作)は2026-07-23に本番適用+push済。残バッチ012-071(~6,000作)は材料キャッシュ有・未生成"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0509a12b-1ce9-452a-8d48-718a7a31e2aa
  modified: 2026-07-23T07:18:35.872Z
---

キャッチ/詳細の分散エンリッチ(対象7,048作=72バッチ)。2026-07-07にセッション枠問題で一括WFは破棄。

- **完了12バッチ(000-011=約1,200作)= 2026-07-23に本番適用+push済**(commit 195c1f908)。
  - 検証: 全1,200作が2巻以上(1巻ゼロ=材料バッチが2巻以上作のみ)→2026-07-14ポリシー(1巻=ジャンルのみ)に抵触せず全作フル適用OKだった。
  - 品質検証クリーン: catch長16-34字/syn長33-114字/catch==syn事故0/master外genre0/既存seed重複0。
  - 純粋追加: catch-ja.json +1166 / synopsis-slug-ja.json +1085 / genre-enrich-2425.json +679。
  - 反映: 1,166 slug文字列=37,793字がWindows引数上限(32,767)超→3チャンク分割で `_reflect-targeted.py --only`(最後だけ--push)。
  - genreは既存trusted/楽天を尊重(空/未ラベルのみ充填)=promote L3168の優先順。
- **残バッチ012-071(~6,000作)= 未生成**。材料は `.cache/enrich-batches/batch-0NN.json`(消えたら `.cache/_prep_enrich_batches.py` 再生成可)。
- 再開手順: 出力の無いバッチ番号だけ生成→出力を `data/enrich-out-2026-07/batch-0NN.json`(dict形式 `{slug:{catch,synopsis,genres_add}}`)→適用は上と同じ(scratchpadの validate_enrich.py / apply_enrich.py が雛形、`.cache/`にbak取得)。
- 生成方式: 一括WF(サブエージェント)はセッション枠を食うため破棄裁定。Opusインライン小分け or API課金側で。
- 全量一括はしない([[enrich-catch-synopsis]] skill が正本)。
