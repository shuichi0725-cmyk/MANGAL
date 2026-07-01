---
name: adult-signal-dbsearch
description: 【adult v3 信号源】adultcomic.dbsearch.net = キュレーション済み・更新頻度高い成年作家/出版社/雑誌リスト。年齢ゲート裏。authors/magazines強・publishers裏取り併用
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

ユーザ提供(2026-06-13)の成年判定 ground-truth 信号源。adult判定v3([[adult-judgment-architecture]])の「adult_score を立てる側」の精度向上に使う(今夜の漏れ=IDコミックス Lake/Rex 等の根因=リスト不足、への対策)。

**URL(3経路)**:
- 作家: `https://adultcomic.dbsearch.net/author/list.html`
- 出版社: `https://adultcomic.dbsearch.net/publisher/`
- 雑誌(出版社別): `https://adultcomic.dbsearch.net/magazine/publisher.html`

**性質(ユーザ談)**: 完璧ではない。**出版社は成年限定でない社も混じる**。ただし**更新頻度が高い**=月次蒸留で再取得して鮮度維持できる。

**使い方の方針**:
- ★**作家リスト・雑誌リスト = 強い信号**(成年作家・成年誌は直接 adult シグナルに使える)。
- ★**出版社リスト = 裏取り併用**(成年専業でない社が混じる → 単独でadult判定に使わず、ISBN出版者記号/レーベル/他シグナルと突合してから)。
- 既存の adult-imprints.yml / adult-publishers と突合し、**未収載の成年作家/レーベルを純粋追加**(今夜見つけた IDコミックス Lake/Rex もここで拾えるはず)。

**収穫の技術メモ**:
- ★**年齢確認ゲートの裏**にある(WebFetchはゲートしか取れない=2026-06-13確認)。収穫スクリプトは Yes遷移 or 年齢確認cookie(例 `over18=yes` 類)を付けて target ページを取る必要がある。
- 月次蒸留の adult 監査ステップに「dbsearch再取得→差分を adult-imprints/authors へ純粋追加」を組み込む候補。

**着手タイミング**: adult v3(楽天収穫完走後 + 今夜の漏れ修正後)。今は記録のみ。
