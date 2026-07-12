---
name: inflight-state-2026-07-12
description: "進行中状態(2026-07-12時点): 週次公開済み・週次待ちの新積み上げ・保留キュー・次のタスク"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7b577e00-f57a-4227-841a-32fbd1f45c6c
---

旧 [[inflight-state-2026-07-10]] を置換。

## 済み(2026-07-12週次で本番公開済み)
週次蒸留2026-07-12完走(65,837頁/PUT132,722全量/smoke10-10)。それ以前の全修正+preorder108頁+検索UI(ボタン確定/人気順既定/戻る復元)公開済み。

## 週次待ち(次の週次で公開される・本番化済み)
- 本番化14頁(手塚全集組4=丹下手塚/シャリ河/牙人/ピロン、丹下左膳3版=横山・小沢、原作者ダンプ分離7=帝都高橋/悪魔Jet/アンナいがらし/オペラ座Jet/犬神いけうち+Jet/野菊知念/剣客さいとう)
- per-case修正: キングダム完全版15-18/RAVE9取り違え(モナ真ISBN 4-06-302950-6)/ふるさと3版再建/スーパーマリオくん全61巻再建(著者=沢田是正)/エビちゅ3版再建+ちゅ〜/失われたムー大陸単巻化/社長とあんあん全22巻(副題埋込数字型)
- コード: AI書評節番号正規化(seed1始まり+−1ハック撤去)/カテゴリタイル改修(人気順左上・交差件数・マージタップ)

## 本番化待ち(preview確認待ちドラフト)
- 嵩瀬ひろし版マリオ2頁(super-mario-kun-color-special全4巻/super-mario-kun-takase2004ぴっかぴか全5かん)
- preview現況=巻抜け仮想レビュー252頁+上記2ドラフト

## 保留キュー(裁定/作業待ち)
- 手塚全集突合: E組ISBNレス旧書27件+B併録4+C版裁定2(docs/production-diagnostics/tezuka-zenshu-missing.tsv)
- 成年triage 871頁=T1専業277/T2兼業115/T3弱472(adult-slipthrough-triage.tsv)=全件目視待ち
- ghost-volumes連番型22頁(戦前作スタブ・NDL日付補完すれば救える)
- 楽天不在49の残(nocover-2024-rest59.tsv: 冬水社POD型/hakoniwa-no-zante=979-8 KDP帯疑い)
- 全集コーナー構想合意済み(A=巻ラベルseed+B=コレクション頁を同一seedで両取り。手塚400→水木→藤子F→石ノ森500の順)
- 索引軽量化の中玉=authors列ダイエット(romaji除去で転送-15〜20%見込み・実測済み)

## 新しい道具(2026-07-11〜12)
- skill tameshiyomi-harvest(試し読み拾って)=BookLive title_id収集。**Sonnet 5運転前提**・裁定のみAI。ボタンUI/中継/via_cd実装は本体の残タスク(seed溜まったら)
- 試し読みビューア=`booklive.jp/bviewer/s/?cid=<title_id>_001`はvia_cd無しで開く(実証済)。シーモアはURL規則不透明=提携後
- force_adult:true(adult-overrides.yml)=すり抜け成年のper-case除外
- 検出パイプ: 副題埋込数字型(社長とあんあん)/ISBN1桁取り違え型(RAVE9⇔モナ)/全集通番誤流入型(ムー大陸v6)/別作者フランケン(マリオくん=嵩瀬混入)

[[adult-slipthrough-class]] [[feedback-one-bug-means-a-class]]
