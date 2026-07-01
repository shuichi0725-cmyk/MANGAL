---
name: discovery-strategy-and-refs
description: discovery=サイト中核価値。競合(manba=コミュニティ先行)と戦わず網羅×カテゴリ×AIで差別化。AniList人気/評価(コミュニティ不要)+ジャンル別ランディング(自動まとめ記事)実装
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★ユーザ表明(2026-06-13): 「漫画を探す・知る・そのまま買える場所へ誘導」が中核目標。**discovery が価値の本体、アフィは収益手段**。コミュニティ系は**やる気なし**(明言)。MANGAL着手前に他アフィ/discoveryサイトは見ていなかった(あえて)。

## 競合・参考調査(2026-06-13)
- **manba(manba.co.jp)**: クチコミ/レビュー+ランキング駆動。ランキングは多シグナル合議(レビュー数/閲覧数/コミュニティ言及/★ストア参照回数/受賞)。本棚・読書記録・フォロー・編集記事「マンバ通信」。= **コミュニティ/ソーシャルプルーフ先行=ユーザ臨界量が要る**。
- **AniList/MAL**: タグ複合×スコア/人気順×relations = 「未知との出会い」UXの手本。我々は既にデータ使用。
- **マンガペディア**: 網羅カタログDBの最近似(発見は弱い=我々のチャンス)。
- **アフィ主流=ランキング/まとめ記事ブログ**(「異世界漫画おすすめ20選」等、人手キュレーション+アフィリンク、SEO流入最大勢力)。

## ★戦略結論(差別化)
- **コミュニティで戦わない**(manbaの土俵に乗らない)。**初日から機能する 網羅カタログ×カテゴリ/ファセット×AI** で差別化。
- ★**まとめ記事を網羅・データ駆動で自動生成** = アフィ主流モデルを凌駕(人手数十記事 vs 全ジャンル自動)。`/genre/[key]` がその器(discovery+SEO+アフィを1ページに集約)。
- ★**コミュニティ不要で「人気/評価」を出す**: manbaはレビューで人気、我々は **AniList popularity/averageScore**(v3 dumpに在る)で代替。
- ★**ストアクリック数トラッキング(Worker)= 収益兼ランキングsignal**(manbaの「ストア参照回数」と同じdual-use)= 将来。

## 実装済み(2026-06-13、commit予定/promote反映中)
- **popularity/score**: enrich(v3由来)→promote→schema。51,244件にpopularity(ONE PIECE 224,863/score91)。「人気順/高評価」discoveryの土台。
- **`/genre/[key]` ランディング**: 全作品をジャンル別・★人気順、score≥70に★バッジ、AI解説スロット(今はデータ駆動暫定文、将来per-genre AIキュレーション差込)。120作表示+「一覧表で全作」リンク。
- 関連: [[genre_quality_improvement]] [[store_affiliate_architecture]] [[feature_roadmap_post_db]]

## 次の候補
- per-genre AIキュレーション文の生成(まとめ記事の解説部分)。
- 人気順をホーム/各所のdiscoveryに活用(運命の一冊・特集の重み付け等)。
- テーマ(AniList tags=異世界/復讐等)を発見の細facetに(タクソノミー増やさず=ユーザ方針)。
