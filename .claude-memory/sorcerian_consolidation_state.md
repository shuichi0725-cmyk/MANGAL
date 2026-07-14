---
name: sorcerian-consolidation-state
description: ソーサリアン統合=本番化済(2026-07-15・週次で公開)。単巻読切連番シリーズ1頁統合の型見本(title_display/alt索引/多人数ガード)
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

## 本番化済(2026-07-15完遂。以下は実施記録)
1. ✅統合頁=preorder-pages+manga.v2昇格済
2. ✅旧9頁=page-dedup恒久drop+manga.v2削除+alias(旧URL→sorcerian・連鎖直結5件込)
3. ✅RelatedWorks=著者5人以上の頁は「同作者」スコア無効(computeRelated manyAuthorsガード)
4. ✅imprint=統合頁がソーサリアンシリーズで統一(旧頁削除で11混入も消滅)

とよ田みのる短編集(toyoda-minoru-tanpenshuu)も同型で適用済み(vol1=CATCH&THROW 2012/vol2=イマジン2020)。
