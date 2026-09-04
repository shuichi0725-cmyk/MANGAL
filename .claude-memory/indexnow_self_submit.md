---
name: indexnow-self-submit
description: IndexNow 自前送信(2026-09-04 ユーザ裁定)=scripts/_indexnow.py。r2-sync→pending→finalize(purge後)drain / feature・diff-deploy は即drain。鍵=public/efa08…txt(公開・非秘密)。Google非対応=sitemapが正
metadata: 
  node_type: memory
  type: project
  originSessionId: 981cfdce-d412-49dd-a505-855ea2bffe35
  modified: 2026-09-04T09:41:35.834Z
---

ユーザ裁定(2026-09-04): 「IndexNow を自前で直接叩く。鍵ファイルを https://mangal-db.com/<key>.txt に設置し、
デプロイスクリプトが実際に変更されたURLを IndexNow API へ POST する」。動機= Cloudflare Crawler Hints は
edge cache の変化を拾う仕組みで、**Worker+R2 配信では発火しない疑い**があるため。

## 実体
- ヘルパー `scripts/_indexnow.py`(単一ソース: 鍵発見・キー→URL写像・pending・送信・記録)。
- 鍵 = `public/efa08a89a5e7a14dc0bde143738fae20.txt`(commit 3b48fce3b で恒久化済・ファイル名=中身)。
  ★**鍵は所有証明であって秘密ではない**(エンジンが取りに来る公開ファイル)。公開リポジトリに在ってよい。
  第三者にできるのは mangal-db.com のURLを送るノイズだけ(エンジンはホスト一致と鍵ファイルを検証)。回す時はファイル名を変える。
- 連鎖(全て try/except・IndexNow の失敗でデプロイは止めない・各 `--no-indexnow` で抑止・`--dry` は到達しない):
  - `_r2-sync.py`(週次) → 差分PUT/prune の `.html` キーを `.cache/indexnow-pending.json` に積むだけ。
  - `_weekly-finalize.py` → **edge purge 後**に drain(=エンジンが取りに来た時に旧キャッシュを掴ませない順序)。
  - `_deploy-feature.py` / `_deploy-differential.py` → 自前 purge+疎通の後に積んで即 drain。
- 写像 `key_to_url`: `.html` のみ(RSC `.txt`/`_next/`/JSON/sitemap 除外)、`index.html`→`/`、`_empty`/`404`/開発面(home-design-*/nav-lab/search-proto 等)除外。selftest あり。
- 送信規約: ≤10,000 URL/POST、`https://api.indexnow.org/indexnow`、200/202=受理、422=ホスト外 or 鍵不一致、429=送りすぎ(5秒待って1回だけ再試行、以降は pending 保持)。
- ★送信前に本番の鍵ファイルが **200 かつ中身一致**か確認し、未配信なら送らず pending に保持(鍵ファイル自体は次の機能蒸留/週次で R2 に上がる。2026-09-04 時点=本番404・preview200)。
- 記録: `.cache/indexnow-pending.json`(未送信) / `.cache/indexnow-log.jsonl`(送信履歴)。手動: `--status` / `--drain [--dry]` / `--urls /a,/b` / `--clear`。

**Why:** 外部被リンクを待つ間に Bing/Yandex 系へ変更を即時に届ける唯一の確実な経路。実測で Bing 流入 > Google。
**How to apply:** デプロイ後に `python scripts/_indexnow.py --status` で pending 0 と鍵OKを見る。Google は IndexNow を読まないので sitemap+内部リンク([[seo_structure_gaps_2026_09_04]])が Google 向けの柱のまま。関連: [[deploy_environments_state]] [[hosting_worker_r2_architecture]]
