---
name: reflect-targeted
description: 反映して=seed/per-case修正を本番manga.v2+テスト環境へ数分で反映(targeted)。フルpromote(3時間)は使わない
---

# 反映して (= targeted反映)

トリガー語: **「反映して」**。per-case修正(数〜数百頁)を数分で反映する既定ルート。
★フルpromote(66k再生成~110分+索引)は週次/月次蒸留のときだけ。

## NEVER
- per-case にフルpromoteを使わない
- 変更slugをユーザに聞かない(**自分で列挙**: 触った seed の key → 対応slug)
- push後の追いpushをしない(previewビルドがcancelされ「変わらない」の正体になる)

## 手順
```
python scripts/_reflect-targeted.py --only <SRC-stem,...> [--drop <消すstem,...>] [--push -m "メッセージ"]
```
- `--only` = **manga.v2ファイル名(SRC slug)**。slug-override頁もSRC名で指定。
- `--drop` = 消す頁(page-dedup/non-manga-drop 登録後に)。manga.v2+preview 削除+索引remove まで自動。
- 内蔵: 検証ゲート(slug/kana/date/isbn 不正で push 前停止)・promote --only・索引 --update/--remove(本番+preview)・preview同期・台帳集約・push。
- 書影は promote に統合済(別工程不要)。

## 反映先の意味
- 本番系列 = data/manga.v2 + data/索引(gitのみ。**本番R2は週次蒸留まで出ない**)
- テスト = .preview-data(pushで自動デプロイ、**反映15-20分・追いpush禁止**)
- preview の頁subsetに無い作品を確認したい時: `cp data/manga.v2/<slug>.yml .preview-data/manga/` + `python scripts/_build-list-index.py .preview-data/manga .preview-data` + push

## 罠
- edition-canonical 結線slug(golgo-13/tsuribaka-nisshi/urusei-yatsura)は edition-overrides を直しても**canonicalが後勝ち**(reflectが警告する) → canonical側を直す
- 新publisherキーを masters に足したら `.preview-data/publishers.yml` にも cp(preview 404の原因)
- 日付は YYYY-MM-DD/YYYY-MM(ゼロ埋め)。全角数字はNFKC
