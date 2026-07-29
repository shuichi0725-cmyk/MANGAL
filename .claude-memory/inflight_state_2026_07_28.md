---
name: inflight-state-2026-07-28
description: "進行中状態(2026-07-28): 次=週次蒸留(wrangler deploy+初--prune込み)・preview=復活815+新刊セット・Kobo書影HOLD33+書影無し21がユーザ裁定待ち・AI書評13節格納済"
metadata: 
  node_type: memory
  type: project
  originSessionId: db595250-4c34-4603-b151-4b5dbb1db69e
  modified: 2026-07-29T11:03:07.060Z
---

旧 [[inflight-state-2026-07-17]] を置換(生き残り保留は下へ引き継ぎ)。

## 次=週次蒸留(ユーザトリガー待ち。今回だけの特記3点)
1. ✅済(2026-07-29家作業): **Workerデプロイ完了**(検索改善4hキャッシュ+304、/go 302中継とも本番反映・302/400/secret生存を実測確認)。根因はCF認証2段崩れ=①.envの解析用トークンをwranglerが誤用(→`CF_ANALYTICS_API_TOKEN`に改名で恒久修正)②OAuth失効(→`wrangler login`で復旧)。さらに**wrangler-r2.jsoncのname=mangalが別Worker**でドメイン付きの本番=**mangal-r2**とズレていた→name修正+MAILER/MAIL_TOバインディング追記(デプロイは設定内容で置換されるため)。★旧Worker「mangal」は残骸(今日のコードが誤アップ済・ドメイン無し)=削除候補。
2. ★**初の r2-sync --prune 回**([[r2-orphan-pages-prune-missing]]の孤児1,041頁+成年drop旧HTML掃除)。削除件数を実行前にユーザへ提示してから流す。
3. 検索回帰 vitest green 必須(2026-07-27改修: 数字揺れfold/head読み/aiLeagueSchedule等254本)。

## preview現況(mangal-preview)
- 中身=**復活815頁+新刊セット**(月次1.2.18の本番待ち。週次で本番公開→preview解放)。
- ★**Kobo書影の目視裁定待ち: HOLD33作**(装丁一致か画像で人が判定)+**書影無し21作**(NDL照会は休養明けに=7/27に429を踏んだ)。DUP5件は既知偽陽性で保留(エスパー魔美/銀河鉄道999/ヰタ・セクスアリス/エルハザード/柏田系)。
- AI書評リーグ=**13節格納済・在庫最終は節13(9/27)**。運用ルールは [[ai-review-league-operation]]。

## 保留キュー(2026-07-29追加)
- ★モブせか共和国編の頁題欠陥: `otome-gee-sekai-wa-mobu-ni-kibishii-sekaidesu`(2巻・2026-01〜)は実体=**【共和国編】**なのに頁題が無印と同名「乙女ゲー世界はモブに厳しい世界です」。題+かな是正(slug再検討含む)のper-case候補。authors欄も5名混载(三嶋与夢/行々狸/孟達/マツリセイシロウ/FTops)=役割整理要。
- 続巻逆照合gap617巻= `docs/production-diagnostics/zokkan-gap-report.tsv`(per-case裁定行き・登録禁止の型)。
- 完結候補hold21作=最終巻発売(2026-08〜10月)後に「完結適用して」で適用(TSVに注記済)。

## 保留キュー(前回から引き継ぎ・変化なし)
- slug裁定1件: 『私の近衛騎士が女装をする理由』楽天ヨミ「オネエナリユウ」→ slug=josouのままか onee-na か。
- 素材ハーベストGO待ち4件(date結線/月ズレhold35,911/hiatus基準/awards結線)=skill material-harvest のGO待ち節が正本。
- 成年triage871頁目視 / 手塚全集E組27冊 / ghost-volumes22頁 / 全集コーナーまとめGO待ち([[zenshuu-corner-state]]) / kobo-gap-skip185作 / FLAG108(genre-other) / 旧検索索引撤去(2026-08目安) / ソーサリアン型の残務なし。
- 種1→種2脱落の救済673series([[seed1-to-seed2-loss-is-mostly-anthology]])と孤児46,874([[orphan-series-promote-is-srcpage-driven]])=種2再ビルド/設計マター・未着手。
