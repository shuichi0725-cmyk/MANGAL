---
name: inflight-state-2026-07-12
description: "進行中状態(2026-07-12夜時点): 週次待ちの新積み上げ(確認済み含む)・保留キュー・次のタスク"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7b577e00-f57a-4227-841a-32fbd1f45c6c
---

旧 [[inflight-state-2026-07-10]] を置換。2026-07-12夜に同日セッション分を追記。

## 済み(2026-07-12週次で本番公開済み)
週次蒸留2026-07-12完走(65,837頁/PUT132,722全量/smoke10-10)。それ以前の全修正+preorder108頁+検索UI(ボタン確定/人気順既定/戻る復元)公開済み。

## 週次待ち(次の週次で公開される・本番化済み)
- 嵩瀬版マリオ2頁(カラースペシャル全4巻・ぴっかぴか全5かん)=本番化済み(preorder-pages恒久)
- ★2026-07-12夜 ユーザpreview確認済み・問題なし: **版並び替え**(VolumeRow=別ISBN刷のタブ分離+書影あり×最大巻数先頭→新しい順→初版最後。うる星パイロット承認=全頁適用で公開) / **アニメ季節コーナー**(トップ今季コーナー+/anime季節別219季・履歴ナビ。データ=AniList全歴史7,130本→3,186結線)
- 同日分(確認不要のコード/データ): 共有ボタン(X/LINE/OS共有、X=twitter.com intentに修正済) / about書影注記 / 真鍋2作(アウトランダーズ・ライ)Kobo書影統一 / **cover-override.jsonl機構**(ISBN→書影の強制上書き・種2不変・可逆) / 試し読みseed(827シリーズ・12,175巻)
- 前からの分: 本番化14頁(手塚全集組4/丹下左膳3版/原作者ダンプ分離7) / per-case修正(キングダム完全版15-18/RAVE9/ふるさと/マリオくん61巻/エビちゅ/ムー大陸/社長とあんあん) / AI書評節番号正規化 / カテゴリタイル改修

## 本番化待ち(preview確認待ちドラフト)
- (無し。嵩瀬版マリオ2頁=2026-07-12夜に本番化済み→preorder-pages恒久・週次待ちへ)
- preview現況=巻抜け仮想レビュー252頁+真鍋2作+うる星(版並び確認用)

## 次のタスク候補(2026-07-12夜時点のおすすめ順)
1. **試し読みボタンUI+中継実装**(seed=tameshiyomi-booklive-volumes.jsonl 12,175巻分が待機。詳細頁に📖ボタン)
2. 週次蒸留(上の積み上げ全部を本番公開)
3. アニメ季節: 保留805本の裁定(ラノベ続編の題ズレ等)+季刊更新トリガー語のskill登録

## 保留キュー(裁定/作業待ち)
- 試し読み保留406件(tameshiyomi-holds.tsv)+人気順828位以降の収集続行
- 手塚全集突合: E組ISBNレス旧書27件+B併録4+C版裁定2(docs/production-diagnostics/tezuka-zenshu-missing.tsv)
- 成年triage 871頁=T1専業277/T2兼業115/T3弱472(adult-slipthrough-triage.tsv)=全件目視待ち
- ghost-volumes連番型22頁(戦前作スタブ・NDL日付補完すれば救える)
- 楽天不在49の残(nocover-2024-rest59.tsv: 冬水社POD型/hakoniwa-no-zante=979-8 KDP帯疑い)
- 全集コーナー構想合意済み(A=巻ラベルseed+B=コレクション頁を同一seedで両取り。手塚400→水木→藤子F→石ノ森500の順)
- 索引軽量化の中玉=authors列ダイエット(romaji除去で転送-15〜20%見込み・実測済み)
- アウトランダーズ愛蔵版/文庫の書影=巻割り違いで未充填(Koboは8巻割りのみ)

## 新しい道具(2026-07-11〜12)
- skill tameshiyomi-harvest(試し読み拾って)=BookLive title_id収集+★**全巻展開--expand**(title_id=シリーズ単位、cid末尾3桁で全巻到達=HEADのみ)。ボタンUI/中継/via_cd実装は本体の残タスク
- 試し読みビューア=`booklive.jp/bviewer/s/?cid=<title_id>_NNN`はvia_cd無しで開く(実証済)。シーモアはURL規則不透明=提携後
- アニメ季節パイプ: `_anime-season-harvest.py --season YYYY-SEASON`(429リトライ内蔵・2.6s/req)→`_anime-season-join.py`→`_build-anime-season-view.py`=季刊入替3コマンド
- cover-override.jsonl(promote機構)=種2に書影があっても上書き(release-date-overrideと同型)
- force_adult:true(adult-overrides.yml)=すり抜け成年のper-case除外
- 検出パイプ: 副題埋込数字型/ISBN1桁取り違え型/全集通番誤流入型/別作者フランケン
- 購入ボタンUI裁定=ハイブリッド型(紙=直ボタン/電子=「電子書籍で買う」→ストアリスト。[[store_affiliate_architecture]])

[[adult-slipthrough-class]] [[feedback-one-bug-means-a-class]]
