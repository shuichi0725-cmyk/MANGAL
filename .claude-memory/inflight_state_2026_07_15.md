---
name: inflight-state-2026-07-15
description: "進行中状態(2026-07-15時点): 本番待ち約2,300頁(ドラフト1,091本番化済+検索v2+西暦rename)・preview=2026-05以降絞り・次=週次蒸留"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6021a518-a36b-44ff-aa0c-31013be82fed
---

旧 [[inflight-state-2026-07-12]] を置換(引き継ぎ分は下の保留キュー)。

## 週次待ち(次の「週次蒸留して」で本番公開・全て本番化/適用済み)
- **予約ドラフト1,091頁本番化**(1,024=数週分レビュー済み+67=7/14日次分。preorder-pages恒久)
- **検索v2+索引v3**(検索索引廃止・一覧共有・authorsパック・fl・head/alt・衛生監査ゲート=[[lightweight_index_architecture]])
- **一覧表の戻る復元**(さらに表示n/並びs=URL・スクロール=sessionStorage)
- **巻title_display表示**(VolumeSchema+VolumeCoverflow=ソーサリアン型の汎用機構)
- 西暦suffix見直し18rename(slug-overrides+aliases=[[slug-collision-year-rule]])・著者中黒分割6件・題末尾「上/（上）」剥離15件・赤塚不二夫語辞典drop(非漫画)・アスペルガー本のNDL改題適用
- 7/14日次分: 続巻40巻(reflect済=本番R2にも出てる)・genre28件付与

## preview現況
- **「最新巻の発売日≥2026-05」絞り=1,253頁**+sorcerian(統合頁hold=[[sorcerian-consolidation-state]])。実体は無傷、絞りは表示のみ。
- ユーザ確認中: 新刊ドラフトの品質(書影無し11件=楽天未掲載の正常系と確認済み)。
- 裁定待ち1件: 『私の近衛騎士が女装をする理由』の楽天ヨミ「オネエナリユウ」(ルビ読みらしい)→slug=josouのままかonee-naか。

## 次のタスク候補
1. **週次蒸留**(上記全部を公開)
2. ソーサリアン本番化(旧9頁畳み込み+RelatedWorksガード=[[sorcerian-consolidation-state]])
3. 旧検索索引の撤去(2026-08目安・キャッシュ失効後)
4. Gemini検品/試し読み=アイドル運転(skill idle-run)

## 保留キュー(07-12から引き継ぎ)
- 試し読み保留6,623裁定+収集続行 / 成年triage871頁目視 / 手塚全集突合E組27冊 / ghost-volumes22頁 / 全集コーナー構想 / kobo-gap-skip185作 / FLAG108(genre-other-flags=画集/評論/対談集等)=ユーザ「あとで」
