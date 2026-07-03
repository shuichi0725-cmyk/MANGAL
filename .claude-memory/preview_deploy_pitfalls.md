---
name: preview-deploy-pitfalls
description: mangal-previewのデプロイ反映の罠(15-20分・連投で前ビルドがキャンセル)とルート構造・確認手順
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

mangal-preview.pages.dev のUI修正で「変わらない」と長時間ハマった反省。

**Why:** プレビューは GitHub Actions `.github/workflows/deploy-preview.yml`(push時、 paths=app/components/lib/public/.preview-data 等)でビルド→`wrangler pages deploy`。 ビルドが**15-20分**かかる(next build 8分+768ページ生成)。 `concurrency: cancel-in-progress: true` なので**新pushが来ると前のビルドをキャンセル**→連投すると永遠に反映されない。 ★ユーザがテストしたのは毎回**完了前**だった。

**How to apply:**
- UI修正をpushしたら **20分待つ**。 その間 **追加pushしない**(前ビルドが死ぬ)。
- デプロイ状況確認 = `gh`は未インストール → **GitHub Actions REST API を curl**: `https://api.github.com/repos/shuichi0725-cmyk/MANGAL/actions/workflows/deploy-preview.yml/runs`(public repo・認証不要)。 head_sha/status/conclusion を見る。
- デプロイ済JSの検証 = `curl <url>/browse` → chunk列挙 → 各chunkをgrepして特徴文字列(例 `catch-clamp`)の有無。 ★**ホーム `/` ではなく `/browse` を見る**(下記)。

**ルート構造(混同注意):**
- **ホーム `/` = `app/home-design-11`**(別デザイン・MarqueeTitle使用)。
- **一覧(診断ボタン+MangaCard+検索結果) = `/browse` = `app/browse/page.tsx` → HomeClient**。 ユーザが「一覧」と言うのはこっち。
- 私はずっと `/` のJSを見て「修正が無い」と誤判定した。

**CSS教訓:** grid/flex item は `min-width:auto` 既定で、 長い無分割テキスト(日本語題)の中身に押し広げられ容器(root)を超えることがある→stickyヘッダーとズレる。 ★**一覧列に `min-w-0`** + body `overflow-x:clip`(sticky非破壊) で封鎖。 [[lightweight_index_architecture]]


## 2026-07-03 stale生成物クラスの教訓(カレンダー)
- ★public/calendar(6/26製)がslug改名後も残置→①launch表示が別作品に化ける(1968-08のK幽霊=実体はこんにちは先生konnichiwa-sensei) ②一覧が生slug表示 ③current月が古い。
- 恒久策: **生成物(public/calendar・public/data/*-stock.json等)は週次蒸留/月次蒸留で必ず再生成**する工程に含める(`_build-calendar.py`+`_gen-corner-stocks.py`)。発売日カレンダーは全期間化済(release 832ヶ月・月戻り可)。
