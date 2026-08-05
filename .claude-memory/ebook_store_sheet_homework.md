---
name: ebook-store-sheet-homework
description: 【宿題】電子書籍ストア一覧シート(マンバ風)=紫パネルの「押せるのに動かない」根治案。各ストアのアフィ申請が通ってから着手
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-05T12:58:17.296Z
---

# 【宿題】電子書籍ストア一覧シート (= 2026-08-05 設計合意済み・実装は保留)

**着手条件**: 電子書籍ストア各社のアフィリエイト申請(バリューコマース等)が通ってから。ユーザ裁定「まだ申請してないところばかりなので宿題として覚えておくだけで良い」。

**問題**: 詳細頁の紫「📱電子書籍で買う」パネルが**ボタンに見えるのに押しても何も起きない**(機能するのは中のKindle/Koboボタンのみ)。グラデ+角丸が押せる見た目をしている。

**合意済み設計**(マンバ風・丸パクリ回避):
- 紫パネル全体をタップ→**ボトムシート展開**→ストア一覧(選択巻連動)から選んで飛ぶ
- 見た目は**ロゴ画像を使わずテキスト+ブランド色チップ**(商標回避+既存カートボタンの作法)
- 中身Phase1: BookLive**商品頁直リンク**(tameshiyomi title_id×巻=25,149作確定済み) / 楽天Kobo(検索g=101) / Kindle(紙dp+切替案内) / ebookjapan・シーモア・BOOK☆WALKER等は検索素リンク
- ★素リンクでも**LinkSwitch**(layout実装済み vc_pid=892673489)が提携承認後に自動収益化=提携が通るたびコード変更ゼロで効き始める
- Phase2: 各ストアID収集で直リンク化(Kobo itemNumber / 電子ASIN=PA-API / ebookjapan等)
- 既存のKindle/Kobo即飛びボタンはシート内 or 近道として維持
- ★試し読みボタン=**実装完了**(2026-08-06 テスト成功→全結線): 選択巻カード直下・白地緑枠・bviewer直開き。ビルド時join=data/tameshiyomi-map.json(25,149作)+lib/tameshiyomi.ts。電子パネルは青5(#3b82f6)確定。**本番公開=次の週次蒸留**(map再生成は週次事前再生成に組込済)。収集はデルタ恒常化(pop0足切り廃止・latest_date降順=新作自動追随)

**関連**: [[store-affiliate-architecture]](LinkSwitch詳細) / カラー版コーナー(Kobo/Kindle/BookLive 3ボタン一覧頁)も別宿題=Phase分け議論済み・「あとで」
