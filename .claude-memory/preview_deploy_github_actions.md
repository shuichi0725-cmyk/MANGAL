---
name: preview_deploy_github_actions
description: preview反映の実体=GitHub Actions deploy-preview.yml(cancel-in-progress)。詰まった時の診断法
metadata: 
  node_type: memory
  type: reference
  originSessionId: 42685a8c-df88-4f7a-b098-77e07b3030ed
  modified: 2026-07-20T03:05:07.600Z
---

preview(mangal-preview.pages.dev)の反映は **Cloudflare Pages Git統合ではなく `.github/workflows/deploy-preview.yml`(GitHub Actions)** で走る。トリガー=branchへのpush + paths一致(`.preview-data/**` `app/**` `lib/**` `public/**` `package.json`等。★`scripts/**`と`.claude/**`は非対象=これらだけのpushはpreviewを再デプロイしない)。中身=npm ci→`tsc --noEmit`→索引をpublic/へstage→`next build`(MANGAL_DATA_DIR=.preview-data)→`wrangler pages deploy out`。

★**`concurrency: cancel-in-progress: true`** = 新pushが進行中/queuedの旧ビルドを問答無用でキャンセル。これが「反映されない/変わらない」の主因。=**追いpush厳禁**([[reflect_protocol_fast]] NEVER)。恒久対策=日次蒸留は中間全部commit止め+最後に1回push(`_reflect-targeted.py --commit-only`)。

## 詰まった時の診断(2026-07-20実戦=全部これで切り分けた)
1. **実配信を直接見る**(ブラウザキャッシュ非依存): `https://mangal-preview.pages.dev/manga-list-index.json?cb=<ts>` を取得し `d[]` 長=作品数。`cf-cache=None`なら origin生応答。ここが期待値と違えば=デプロイ未更新(ブラウザキャッシュの話ではない)。
2. **Actions実行結果**(gh未インストール・repoはpublic=認証不要): `https://api.github.com/repos/shuichi0725-cmyk/MANGAL/actions/workflows/deploy-preview.yml/runs?per_page=8` → 各runの status/conclusion。cancelled連発=追いpush / queuedのまま=runner待ち。
3. **GitHub稼働**: `https://www.githubstatus.com/api/v2/components.json` の"Actions"。partial_outage等ならrunnerが拾わずqueued長期化(2026-07-20実例=25分足止め→復旧後success)。
4. デプロイsuccess直後でも**数十秒〜数分の伝播ラグ**で旧配信が残る=少し待って再probe。

## 結論の型
データ/索引/commitが正でも「反映されない」なら、まず①実配信probe→②Actions runs→③GitHub status の順。原因は大抵 追いpushによるcancel連鎖 か GitHub側障害。**pushで直そうとしない**(queued生存分をキャンセルするだけ)。関連=[[reflect_protocol_fast]] [[preview_deploy_pitfalls]]
