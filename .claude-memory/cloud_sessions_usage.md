---
name: cloud_sessions_usage
description: Claude Code クラウドセッション(2026-09 一般提供)をMANGALで使う時の要点=作業ブランチ直push・その間ローカルpush禁止・page.preview.tsxでテスト環境専用頁・データ作業は不可・クレジット11/5失効
metadata:
  type: project
---

- ユーザは Pro の100ドル分クレジットを受領(クラウドセッション専用・**11/5 失効**)。残高の見方は不明(記事に記載なし)。
- ★クラウドにあるのは GitHub の中身だけ。`data/manga.v2`(gitignore)・.cache(楽天1.2GB等)・API鍵・R2認証は無い
  = 反映/蒸留/照会/デプロイは不可。コードだけで完結する作業(UI・script修正・テスト)向き。リポジトリは public=PRも公開。
- テスト環境(mangal-preview)に出すには `claude/manga-database-affiliate-3x0ms` へ push が要る(deploy-preview は同ブランチのみ)。
  → クラウド作業中は**ローカルで push しない**・終わったら `git pull --ff-only` で取り込む。push は最後に1回(追いpushでビルド中断)。
- 本番に出さない実験頁 = ファイル名 `page.preview.tsx`(next.config.ts の pageExtensions が MANGAL_DATA_DIR=.preview-data の時だけ認める。
  2026-09-26 クラウドが導入)。週次/機能蒸留のビルドでは頁が作られない。
関連: [[magic_shelf_virtual_bookstore]] [[preview_deploy_github_actions]]
