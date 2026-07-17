---
name: inflight-state-2026-07-17
description: "進行中状態(2026-07-17): 本番待ち約2,300頁+完結適用2,082件・次=週次蒸留(manifest復元も兼ねる)・preview=2026-05以降絞り・新PCへ移行済み"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

旧 [[inflight-state-2026-07-15]] を置換(引き継ぎ分は下の保留キュー)。

## 週次待ち(次の「週次蒸留して」で本番公開・全て本番化/適用済み)
- **予約ドラフト1,091頁本番化**(1,024=数週分レビュー済み+67=7/14日次分。preorder-pages恒久)
- **検索v2+索引v3**(検索索引廃止・一覧共有・authorsパック・fl・head/alt・衛生監査ゲート=[[lightweight_index_architecture]])
- **一覧表の戻る復元**(さらに表示n/並びs=URL・スクロール=sessionStorage)
- **巻title_display表示**(VolumeSchema+VolumeCoverflow=ソーサリアン型の汎用機構)
- 西暦suffix見直し18rename(slug-overrides+aliases=[[slug-collision-year-rule]])・著者中黒分割6件・題末尾「上/（上）」剥離15件・赤塚不二夫語辞典drop(非漫画)・アスペルガー本のNDL改題適用
- 7/14日次分: 続巻40巻(reflect済=本番R2にも出てる)・genre28件付与
- ★**完結適用2,082件**(7/17 commit 3f640371b = status既定の証拠ベース化。S側2,082完結化 / F側1,828を連載中へ復帰)
- ★**週次は r2-manifest の復元も兼ねる** = [[r2-manifest-corrupt-pending-repair]](それまで「差分反映して」はabort=正常)

## preview現況
- **「最新巻の発売日≥2026-05」絞り=1,253頁**+sorcerian(統合頁hold=[[sorcerian-consolidation-state]])。実体は無傷、絞りは表示のみ。
- 裁定待ち1件: 『私の近衛騎士が女装をする理由』の楽天ヨミ「オネエナリユウ」(ルビ読みらしい)→slug=josouのままかonee-naか。
- ★7/17日次分の確認待ち: 新作ドラフト3件(femme-fatale-o-meshiagare/zieina-drive=表紙ロゴ公式英字で裁定済/saka-no-aru-machi)。
- ~~stub層data/manga復旧~~ → ★**7/17解消済み**(旧PCcopy69,906件・検証6/7完全一致・D:\mangal-cache\stub-mangaへ保険ミラー=[[pc-migration-2026-07-17]])。

## 次のタスク候補
1. **週次蒸留**(上記全部を公開 + manifest復元)
2. ソーサリアン本番化(旧9頁畳み込み+RelatedWorksガード=[[sorcerian-consolidation-state]])
3. 旧検索索引の撤去(2026-08目安・キャッシュ失効後)
4. Gemini検品/試し読み=アイドル運転(skill idle-run)

## 保留キュー(07-12から引き継ぎ)
- 試し読み保留6,623裁定+収集続行 / 成年triage871頁目視 / 手塚全集突合E組27冊 / ghost-volumes22頁 / 全集コーナー構想 / kobo-gap-skip185作 / FLAG108(genre-other-flags=画集/評論/対談集等)=ユーザ「あとで」
- 環境: [[pc-migration-2026-07-17]](= 新PCへ移行済み。Defender除外だけ未確認)
