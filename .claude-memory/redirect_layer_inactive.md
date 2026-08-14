---
name: redirect_layer_inactive
description: 【重大・未修正】slug-aliasesの301リダイレクトは本番でもpreviewでも実質機能していない(KV未投入+パス形状違い)
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-08-14T02:11:10.357Z
---

2026-08-14 実測で判明。`data/slug-aliases.yml`(31,224件)→ `public/_redirects` の 301 は**どこでも役に立っていない**。

- **本番(Worker+R2)**: `workers/r2-serve.js` は `env.REDIRECTS` から KV `redirects.json` を読む設計だが、**その JSON を生成するスクリプトが repo に存在しない**=KV未投入。実測 `https://mangal-db.com/kotaro-wa-hitorigurashi` は **301せず404**。
- **preview(Cloudflare Pages)**: `_redirects` は native に効くので **301は発火する**。しかし宛先が悪い。
- **★パス形状**: `_gen-redirects.py` は `/旧slug /新slug 301` と**ルート直下**で書くが、漫画頁は **`/manga/<slug>`**。実測 preview `/asataro-den` → 301 → `/asatarou-den` → **404**。ルート直下に `[slug]` ルートは無い(`app/` に存在しない)。

**Why**: slug rename / 頁drop のたび alias を積んできたが、301が届いているか誰も実測していなかった。SEOの被リンクと既存URLは現状すべて404に落ちている。

**How to apply**: リダイレクトの話が出たら「まず効いていない」を前提に置く。修復には2点セットが要る — ①`_gen-redirects.py` の出力を `/manga/<旧> /manga/<新>` に変える(既存31,224件の全書き換え) ②本番用に `redirects.json` を生成して KV へ投入する工程を週次に足す。どちらもコード変更でユーザ裁定待ち(2026-08-14時点で未着手)。

データ側の腐りは 2026-08-14 に一掃済み(削除422/付替53、死に転送0・衝突0)。再発は `_weekly-preflight.py` の 8b「リダイレクト衛生」がFAILで止める。★特に危険だったのは **aliasキーが実在の公開slugと衝突**していた51件(転送が効き出した瞬間に `/devilman` 等の実頁が消える)= 修復を入れる前に必ず衝突0を確認すること。

関連: [[drop_page_redirect_chain]] [[pending_r2_prune_ledger]] [[hosting_worker_r2_architecture]] [[deploy_environments_state]]
