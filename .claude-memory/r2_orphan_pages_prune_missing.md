---
name: r2_orphan_pages_prune_missing
description: "r2-syncは--prune無しが既定=dropした頁が本番に残る。2026-07-27の週次で--prune組込+実削除322。★孤児数の照合はslugで行う(stem照合は誤り)"
metadata: 
  node_type: memory
  type: project
  originSessionId: dff8a305-89f9-41d1-baa4-d9b9d0478784
  modified: 2026-11-10T15:39:52.281Z
---

★**本番サイトから消したはずの頁が消えていない**(2026-07-26 発見)。

## 事実
- `scripts/_r2-sync.py` は **`--prune` を付けた時だけ**「ローカルに無いキー」をR2から削除する。
- ★**週次蒸留 skill の実行行は `python scripts/_r2-sync.py --bucket mangal-site`** = **prune無し**。
  → drop した頁の HTML は R2 に残り、URLは200のまま生き続ける。
- 実測(2026-07-26): この日のフィルムコミック掃引で落とした45頁のうち**35頁が公開中**だった。
- ★**「孤児1,041頁」は誤り。 真値は 322キー**(2026-07-27の週次prune実測)。 誤った理由 =
  **R2のキーは slug なのに `data/manga.v2` の ファイル名(SRC stem) と突合した**ため、
  slug上書きのある頁(例 kamuigaiden.yml → slug kamui-gaiden)を全部「孤児」に数えていた。
  ★以後この種の照合は **必ず yml 内の slug フィールド**で行う(ファイル名 ≠ slug)。

## 効く場面
- 非掲載判定(非漫画/フィルムコミック/重複)を下しても**サイト上は残る**ので、監査の「本番から消えた」は
  data/manga.v2 の話であって公開状態ではない。 [[feedback_production_deploy_gate]]
- Googleにインデックス済みのURLが残るため、消したい頁ほど残る。

## ★対処済み(2026-07-26 ユーザ指示で週次に組込)
- `_r2-sync.py` に安全弁を実装: **`--prune-floor 0.9`**(out/のmanga頁が前回の90%未満なら削除中止=
  build途中失敗の全消し防止) / **`--prune-max 3000`**(超過なら削除せず報告) / 削除キーを
  `.cache/r2-pruned-<日時>.txt` へ実行前に記録。 判定は `--dry` でも表示される。
- **weekly-distill skill の実行行を `--prune` 付きに変更**。
- ★**2026-07-27の初回prune実績 = 322キー削除**(見込み2,100は上記の照合ミス由来の過大見積り)。
  もののけ姫/となりのトトロ/千と千尋/十二国記 が本番で404化したのを実地確認済み。
  中止された時はログを確認し `--prune-max <件数+100>` で再実行する。

## ★残りの孤児を一掃(2026-11-11・完了)
- R2 全186,390キーを台帳(r2-manifest 185,529)と突合 → **孤児861キー・35.5MB**(全部 7/3〜7/17 のPUT =
  prune導入前の残り。 7/27以降の週次では新規孤児ゼロ = 仕組みは効いている)。
- 内訳: 漫画364頁(うち**116頁が本番200のまま**・248頁は301転送で不可視)+古い_next 130+その他3。
- 退避 `.cache/r2-orphan-bak-20261111/` → 削除 → edge purge → 116頁の404を実地確認。
  記録 = `data/seeds/r2-orphan-prune-changelog.jsonl` / 一覧 `docs/production-diagnostics/r2-orphan-prune-2026-11-11.tsv`。
- ★**容量対策にはならない**(R2 10.1GB はほぼ全部が現役。 無料枠10GB超過は月数円)。
- ★調べ方 = `list_objects_v2` 全走査(約190回のClass A)で「R2に在り台帳に無いキー」。 台帳起点の prune は
  **台帳に載っていない孤児を永久に見ない**ので、この全走査だけが見つける手段。
- ★同日: Norton の通信検査で boto3 だけ SSL エラー → `_r2_manifest.ensure_ca_bundle()` で恒久対処
  (週次/差分反映/機能蒸留の3本。 NODE_EXTRA_CA_CERTS の根証明書を AWS_CA_BUNDLE に足す)。

## ★孤児の第2の発生源 = 差分反映のDELETEがstem指定だった (2026-09-04 発見・是正済)
prune 漏れとは別に、`_deploy-differential.py` の DELETE が **SRC stem** キーを消していた
(PUT は公開slug)。 stem≠slug の 1,759頁/69,223頁 では**空振りして本物がR2に残る**。
= 「週次で prune すれば拾える」ので恒久的な穴ではないが、**差分反映では消えない**ことになる。
実測4頁が該当。 是正= `resolve_pub_slug()` で公開slugに解決してから DELETE/purge/IndexNow通知。
詳細と実装見本は [[pubslug_src_stem_generator_trap]] / [[indexnow_self_submit]]。
