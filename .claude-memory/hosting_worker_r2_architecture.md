---
name: hosting_worker_r2_architecture
description: 公開時ホスティング=Cloudflare Worker+R2方式(Pagesでなく)。69kページ≈14万ファイルがPages上限(無料2万/有料10万)を超えるため。R2は実質0円/月、差分アップ可、geo/API/redirect統合
metadata:
  node_type: memory
  type: project
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★**公開時アーキテクチャ方針(2026-06-10 ユーザ合意): Cloudflare Pages でなく Worker+R2**。全部Cloudflare内(他社移行ではない)。

**理由(Pagesが詰む)**: Next.js static export は1ページ= .html+.txt(RSC)の2ファイル → 69kページ≈**14万ファイル**。Pages上限=無料2万/★有料10万(2026-01-23拡大、要 `PAGES_WRANGLER_MAJOR_VERSION=4`)→ **有料でも入らない**。上限は「1回のアップ量」でなく**サイト全体のスナップショット総数**(分割アップ不可、ユーザ確認済)。

**構成**: 訪問者 → **Worker(配信+受付)** → **R2(HTML倉庫、ファイル数無制限)**。同じWorkerに統合: ①geo判定(adult_usの出し分け=静的では全員に物理存在するため遮断はここ) ②動的API層(`/api/cover/:isbn` 楽天書影/在庫/電子割引… ISBNキー) ③301リダイレクト(slug-aliases)。

**R2料金(公式、2026-06確認。記事サイトの数字は不正確なので公式を信じる)**:
- Class A(PUT/POST/LIST)=無料100万/月、超過$4.50/100万 / Class B(GET)=無料**1,000万/月**、超過$0.36/100万 / **DELETE無料・エグレス(転送)完全無料** / ストレージ無料10GB、超過$0.015/GB月。
- MANGAL試算: 初回14万PUT(枠の14%)/月次蒸留は数千PUT/閲覧はキャッシュ無しでも**月300万PV級まで無料**(CDNキャッシュ前段でさらに1/10以下)/サイト数GB<10GB → ★**実質0円/月**。

**利点**: ファイル数無制限 + ★**差分アップロード可**(Pagesは毎回全量、R2は変更ファイルのみ=月次蒸留と相性◎) + geo/API/redirectの一元化。
**引き換え**: 配信Worker(req→R2→キャッシュ制御)とデプロイスクリプト(out/→R2同期)を自作(一度きりの小工事)。Pagesのプレビュー URL等は失う。

**関連する構造課題(同時期に対処、2026-06-10洗い出し)**: ①★トップページが全DB(69k)をHomeClient propsで送る=数十MBで死ぬ → **軽量検索索引の別ファイル化+遅延ロード**が必須 ②検索matchTextがO(n)全件線形 ③promoteの旧sourceページ(data/manga)起点依存=slug再生成時に種2+seeds直接生成へ。
