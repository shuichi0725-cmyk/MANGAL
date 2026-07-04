---
name: display-bug-triage
description: 「表示がおかしい」報告の切り分け手順。環境特定→キャッシュ→stale生成物→データ実体の順で1往復診断
---

# 表示不具合の切り分け (= スクショ/「〜がおかしい」報告を受けたら)

今日の実例で各1往復に短縮できた型: カレンダーK幽霊・生slug表示・灰色書影・臨場の別作化け。

## 手順(上から順)

### 0. どの環境を見ているか(URLで確定)
- `mangal-preview.pages.dev` = テスト(.preview-data push・**反映15-20分・subset**)
- `mangal-r2.shuichi0725.workers.dev` = 本番(週次蒸留/差分反映のみ更新)
- 本番の報告 = 「旧ビルドの内容」の可能性を最初に疑う(直近の修正はテストにしか無い)

### 1. キャッシュか実体か
- 本番HTML/JSONは edge cache 最長1日 → `?v=xxx` を付けて再現するか確認
- preview は push 後15-20分待ったか・追いpushでビルドcancelされていないか

### 2. ★stale生成物クラスか (= 頻出の真犯人)
生成物は再生成しない限り古いまま。対象と再生成コマンド:
| 生成物 | 症状例 | 再生成 |
|---|---|---|
| public/calendar | 旧slug参照で別作品表示(K幽霊)・生slug・月が古い | `_build-calendar.py` |
| public/data/*-stock.json | 書影灰色(slim未展開)・本番に無い作品 | `_gen-corner-stocks.py` |
| public/data/anniversaries等 | 周年/豪華版が古い | `_gen-corner-auto.py` |
| 本番索引(data/) | 消した頁の亡霊が一覧/新刊に出る(レンガ型) | `_build-list-index.py data/manga.v2 data` |
| .cache/isbn-page-index.json | 存在チェックの誤答 | `_exists.py --build` |

### 3. 環境仕様の「正常」を誤報しない
- **preview のカレンダー/コーナーで大半が照合失敗するのは正常**(索引がsubset)
- 索引の疎通確認URLは**ルート直下** `/manga-list-index.json`(/data/ ではない)
- 旧カバー巻の書影無し(1980年代等)は楽天に画像が無い=正常

### 4. データ実体(ここで初めてymlを見る)
- 該当頁 dump(editions×volumes×ISBN帯×日付) → percase-fix skill の型分類へ
- ISBNの正体確認は `python scripts/_lookup.py --isbn ...`(external-data-access skill)

### 5. UIコード
- flex内の画像伸縮=コンテナに `self-start`+ボタンはカード欄外、の前例(LikeButton)
- client componentはHTMLに文言が出ない(周年等)→grep不発は異常ではない。JSON配信200を確認

## 報告様式
「環境=どこ / 真因=上のどの層 / 直したもの / ユーザが確認する場所」の4点で返す。
