---
name: preview_deploy_pitfalls
description: 【事実】preview反映15-20分/追いpushでビルドcancel等の実測。運用のやり方は skill test-deploy / display-bug-triage が正
metadata:
  node_type: memory
  type: project
---

★やり方の正 = **skill test-deploy**(投入手順) / **skill display-bug-triage**(表示不具合の切り分け順)。

## 実測事実(skillの根拠)
- mangal-preview反映=push後15-20分。連投すると前ビルドがcancelされ「変わらない」ように見える。
- 確認はActions REST API。一覧=/browse(HomeClient)・ホーム=home-design-11。grid item は min-w-0 でヘッダーズレ封鎖済。
- previewの索引はsubset=カレンダー等の照合失敗は正常。

## 2026-07-03 stale生成物クラスの教訓(カレンダー)
- public/calendar(6/26製)がslug改名後も残置→①launch表示が別作品に化ける(1968-08のK幽霊=実体はこんにちは先生) ②一覧が生slug表示 ③current月が古い。
- 恒久策: 生成物(public/calendar・public/data/*-stock.json等)は週次/月次蒸留で必ず再生成(`_build-calendar.py`+`_gen-corner-stocks.py`+`_gen-corner-auto.py`)。発売日カレンダーは全期間化済(release 832ヶ月・月戻り可)。カレンダーは title 埋め込み式に変更済(索引join非依存)。
