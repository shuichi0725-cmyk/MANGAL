---
name: deploy-environments-state
description: 公開環境2系統=本番(Worker mangal→R2予定)とテスト(Pages mangal-preview)。URL/アカウント/Pagesデプロイ手順/詰まりどころ
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★**2026-07-10 現況更新**: 本番=**mangal-db.com**(Worker `mangal-r2`+R2配信・ドメイン紐付け済・疎通200確認)。下の「Worker mangal→workers.dev・R2移行が別タスク」の節は**歴史**(R2移行済)。
★**SEO/一般衛生=済(2026-07-10 実測確認・再提案するな)**: GSC登録済(**DNS TXT方式**=`google-site-verification=oXIq...`がDNSに現存。リポジトリ/HTMLに痕跡が無くても未登録と即断しない) / robots.txt(sitemap参照) / sitemap.xml / JSON-LD / OGP / ストアリンク[PR]表記。★未実施=Cloudflare Web Analyticsビーコン(訪問者/人気ページ用・ユーザ裁定)と外形監視(当面不要=ユーザ判断)。

Cloudflare に2系統。 **本番=Worker / 見た目テスト=Pages** で使い分け(2026-06-14 ユーザ確定)。

- **本番** = Worker `mangal` → `https://mangal.shuichi0725.workers.dev`（アカウントサブドメイン=shuichi0725、account_id=`774e95ed884a48e76ffb5aa78ae7e037`）。
  - 現状=**古い部分デプロイのみ**(トップ200/深いページ404)。 native **Workers Builds(Git連携)** がフル66kをビルド→Workers Assets上限(2万ファイル/metadata1MiB)で**失敗し続け＝失敗メール常発**。
  - 本番化=**R2移行が別タスク**: 全66kをR2バケットへ→ worker.js を env.ASSETS でなく **R2取得(env.BUCKET.get)** に書換え→デプロイ。 R2はファイル数無制限＋Workerでgeo/redirect/API。 [[hosting_worker_r2_architecture]]
  - 掃除候補: R2まで上のWorkers Buildsは無駄に失敗するので Cloudflare→mangal→Settings→Builds を一時停止/解除推奨。

- **見た目テスト** = Cloudflare **Pages** `mangal-preview` → `https://mangal-preview.pages.dev`。 600件サブセット。
  - ★**デプロイ方法 = ブランチ(claude/manga-database-affiliate-3x0ms)へ git push するだけ**。 `.github/workflows/deploy-preview.yml` が自動でビルド(`MANGAL_DATA_DIR=.preview-data npm run build`)→ `wrangler pages deploy out` する。トークンは **GitHub Secrets(CLOUDFLARE_API_TOKEN/ACCOUNT_ID)** を使う=**ローカルにトークン不要**。
  - ★**発火パス(これらを変更してpushすれば自動デプロイ)**: `.preview-data/**` / `app/**` / `components/**` / `lib/**` / `public/**` / `next.config.ts` / `package*.json` / `worker.js` / `wrangler.jsonc`。 つまり**UIコンポーネント修正のpushだけで自動デプロイされる**。 `workflow_dispatch` で手動起動も可。
  - ★★**ローカルで `wrangler pages deploy` を叩こうとしない**(.env.localにCFトークンが無く `CLOUDFLARE_API_TOKEN` 必須エラーになる=私が何度も踏む罠)。**push=デプロイ**。 実行確認は `gh run list --workflow=deploy-preview.yml`(gh未導入の環境あり→GitHubのActionsタブ/失敗メールで確認)。
  - データ実体: `.preview-data`(600 yml+masters+seeds, リポジトリ同梱。 art-booksシンボリックリンクは除外/gitignore)。

★Pagesデプロイで踏んだ罠(再発防止):
1. Workers Assets は登録metadata **1MiB上限(code:100145)** = 多ファイル×長slugで超過 → **Pagesに切替**で回避(Pagesは本制約なし)。 main+ASSETS binding/wrangler最新/.txt削除では解決せず。
2. `wrangler pages deploy` は非対話だとプロジェクト自動作成しない → **先に `wrangler pages project create <name> --production-branch=main`**(無いと code:8000007 Project not found)。
3. Workers用 `wrangler.jsonc` は `pages deploy` と混線 → CI上で一時退避(mv)してから実行。
4. トークン **「mangal deploy」に Pages:Edit 権限**を追加済(これが GH Secret CLOUDFLARE_API_TOKEN)。 別トークン「mangal build token」はWorkers Builds用。
5. 大量Actions/メールで追えない時 → **失敗メール本文にエラー全文**が入る(それで取得可)。

全66kフル本番は Pages不可(ファイル上限)= R2必須。 Pagesはあくまでプレビュー常設。
