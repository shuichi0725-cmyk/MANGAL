---
name: redirect_layer_inactive
description: 【✅2026-08-14修復済】301リダイレクト層=KV REDIRECTS+/manga/形状で本番稼働。週次でKV同期(_kv-redirects-sync.py)
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-17T01:24:23.959Z
---

2026-08-14 発見→同日修復完了。`data/slug-aliases.yml`(31,224件)の301は長らく**どこにも届いていなかった**(①本番=KV `redirects.json` 未投入 ②パス形状がルート直下 `/旧` で実頁は `/manga/<slug>`)。実測 `/manga/kotaro-wa-hitorigurashi` → **301 → 200** で復旧確認済み。

**現行の仕組み**(修復後):
- 正本 = `data/slug-aliases.yml`。`scripts/_gen-redirects.py` が **`/manga/<旧> /manga/<新>` 形状**で `public/_redirects`(preview用・Pages静的上限2,000行=部分カバー) と `.cache/redirects.json`(本番KV用・全件) の両方を生成。
- 本番 = KV名前空間 `REDIRECTS`(id `eef1c88ee77340afa67bf78f7e4b9782`、wrangler-r2.jsonc 結線済)。投入 = `python scripts/_kv-redirects-sync.py`(gen再実行→検証→wrangler kv put。OAuth前提)。Worker(`workers/r2-serve.js`)は 6h TTL で再読込+末尾スラッシュ許容。
- **週次蒸留 手順4 で r2-sync `--prune` とセットで KV同期**(= 旧頁実体が消えるのと同じ週に301が引き継ぐ=404の窓なし)。
- 番人 = `_weekly-preflight.py` 8b が 死に転送/衝突/自己参照に加え **形状同期**(ymlと`_redirects`の/manga/1:1)もFAIL化。
- 追記系スクリプト(`_isbn-dup-apply.py` 等4本)も `/manga/` 形状に追随済。

**Why**: aliasを積むだけで実測しておらず、SEO被リンク・既存URLが全部404に落ちていた。修復前の掃除で aliasキーが公開slugと衝突する51件を先に削除してあった(衝突が残ったまま有効化すると実頁が隠れる)= **転送層を有効化する前に必ず衝突0を確認**、が教訓。

**★KV同期は週次のr2-sync後にのみ実行**(2026-08-17実害): rename後の新slugは週次まで本番R2に無い。週の途中でKVを更新すると「旧URL→未deploy新slug」の301=404窓ができる(実測=約900件404化。GSCエクスポートの検証で発覚)。応急処置として**本番生存probe(ブラウザUA必須=素のUAはCloudflareが403)でdead宛先を除外した縮小map(30,298件)を投入済み**。次の週次のKV同期(全件再生成)で自動的に完全体へ戻る。_gen-redirects.py は連鎖平坦化済み(1997→ochi-1994→ochi型を1ホップ化)。

関連: [[drop_page_redirect_chain]] [[pending_r2_prune_ledger]] [[hosting_worker_r2_architecture]] [[deploy_environments_state]]
