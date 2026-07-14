---
name: sorcerian-consolidation-state
description: ソーサリアン統合頁=preview保留中。トリガー「ソーサリアン本番化して」=旧9頁dedup+alias+RelatedWorks多人数ガードとセットで昇格
metadata: 
  node_type: memory
  type: project
  originSessionId: 6021a518-a36b-44ff-aa0c-31013be82fed
---

**単巻読切の連番シリーズは1頁統合**(2026-07-14会議決定・ソーサリアンで型を確立)。

## 統合頁の形(previewの sorcerian.yml が実体・drafts側にも同内容)
- slug=sorcerian・通番1-15巻(1-12=ソーサリアンシリーズ、13-15=新シリーズ)・著者14人・角川書店1988-92。
- **巻の個別題=汎用フィールド`title_display`**(VolumeSchemaに正式追加済): `"副題(著者)"` +新シリーズは`〔新1〕`を付す。巻詳細パネル(VolumeCoverflow)の第N巻見出し下に表示。
- 頁上部: 副題=短い構成説明・別名=英語Sorcerianのみ(15題列挙はくどい=ユーザ裁定)。
- **検索性**: 索引ビルダーが巻title_displayから括弧書きを剥いだ純副題をalt索引へ拾う汎用拡張(どの巻題でも検索ヒット)。
- 発売日=参照サイト(tk-nz.game.coocan.jp COMIC欄)で全巻年月日化済み。書影=Kobo3巻分のみ。

## 残作業(トリガー「ソーサリアン本番化して」で着手)
1. 統合頁を本番へ(現在は本番化のたびに`.cache/`へ退避するhold運用=[[productionize-drafts]] skill参照)
2. **旧9頁の畳み込み**(ten-no-kamigami-tachi等が本番に残存=そのまま出すと重複)+旧slug→sorcerianのalias
3. **RelatedWorksの多人数ガード**(著者5人以上の頁は自欄の同作者スコアを無効化=14著者の関連作品欄汚染対策・約3行)
4. imprint表記の統一(戦国ソーサリアンの`11`混入是正)

とよ田みのる短編集(toyoda-minoru-tanpenshuu)も同型で適用済み(vol1=CATCH&THROW 2012/vol2=イマジン2020)。
