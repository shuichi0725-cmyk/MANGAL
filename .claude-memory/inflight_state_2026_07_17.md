---
name: inflight-state-2026-07-17
description: "進行中状態(2026-07-17): 本番待ち約2,300頁+完結適用2,082件・次=週次蒸留(manifest復元も兼ねる)・preview=2026-05以降絞り・新PCへ移行済み"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

旧 [[inflight-state-2026-07-15]] を置換(引き継ぎ分は下の保留キュー)。

## 週次待ち → ★2026-07-17夜 週次蒸留で全て公開済み
- ドラフト1,094頁(1,091+日次3)・完結適用2,082件・検索v2+索引v3・一覧戻る復元・巻title_display・西暦rename等・成年drop2頁の索引消滅 = 全部本番ライブ(put136,599/smoke10PASS)。
- r2-manifest=ETag照合で復元済み(補完871/退避r2-manifest-bad-20260717-200553.json)。差分反映(diff-deploy)も基準リセット済みで使用可。
- ★成年drop2頁(mainichi/red-dragon)の旧HTMLはR2に残存(直URLのみ・索引不在)。次回--prune判断で掃除可。

## preview現況
- ★**preview=空(解放済み)**。日次7/17ドラフト3頁は本番化済み(preorder-pages恒久+manga.v2+索引=週次待ち)。mainichi/red-dragonは成年ドロップ済(公開消滅は週次)。
- ★アダルトスキャン①②=**完了**(triage837×1,853ISBN→835頁が楽天一般流通/partial2/absent0。TSV=adult-scan-rakuten.tsv。対照=真成年4冊はAPI不在。ドロップ/override適用は未実施=ユーザ確定待ち)。
- 裁定待ち1件: 『私の近衛騎士が女装をする理由』の楽天ヨミ「オネエナリユウ」(ルビ読みらしい)→slug=josouのままかonee-naか。
- ~~stub層data/manga復旧~~ → ★**7/17解消済み**(旧PCcopy69,906件・検証6/7完全一致・D:\mangal-cache\stub-mangaへ保険ミラー=[[pc-migration-2026-07-17]])。

## 素材ハーベスト(2026-07-17新設=アイドル柱⑤・skill material-harvest)
- 初回: 日付候補98,642(seed収集済・★promote結線GO待ち)/月ズレhold35,911(裁定待ち)/wiki記事3,478結線(在庫≒46分=アイドル主食)/賞=作者196・作品68(海外賞込み)
- fish-residue=鍵解消済み・稼働可(deny=Amazon/楽天・サイト台帳簿記)
- GO待ち4件はskill本文のGO待ち節が正本(date結線/月ズレ/hiatus基準/awards結線+賞名マスター)

## ~~週次蒸留=実行中~~ → 完了(下記)
- 事前再生成+preflight済み→**フルビルド走行中**(C:完結・.cache/_wkbuild.ps1をStart-Process起動・logは.cache/weekly-build.log)。
- ★今回からビルドは**C:完結**(ユーザ裁定=ジャンクション全廃・D:はバックアップ倉庫のみ。D:ストール実害が契機。preflight/skill/deploy-differential改訂済みcommit 01a736b1f)。
- 残手順: sitemap→r2-sync(.cache/_r2sync.ps1=★破損manifestのETag復元が今回発動)→purge→finalize→報告。
- 中断/再起動した場合: ビルドlog確認→未完なら再ビルド(再開機構なし)。

## 次のタスク候補
1. **週次蒸留**(上記全部を公開 + manifest復元)
2. ソーサリアン本番化(旧9頁畳み込み+RelatedWorksガード=[[sorcerian-consolidation-state]])
3. 旧検索索引の撤去(2026-08目安・キャッシュ失効後)
4. Gemini検品/試し読み=アイドル運転(skill idle-run)

## 保留キュー(07-12から引き継ぎ)
- 試し読み保留6,623裁定+収集続行 / 成年triage871頁目視 / 手塚全集突合E組27冊 / ghost-volumes22頁 / 全集コーナー=収集済み・まとめGO待ち([[zenshuu-corner-state]]) / kobo-gap-skip185作 / FLAG108(genre-other-flags=画集/評論/対談集等)=ユーザ「あとで」
- 環境: [[pc-migration-2026-07-17]](= 新PCへ移行済み。Defender除外だけ未確認)
