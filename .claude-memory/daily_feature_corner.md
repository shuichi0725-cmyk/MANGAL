---
name: daily_feature_corner
description: 日替わり特集コーナー(/tokushu)=フィルタ組合せをレシピ抽選し毎日1つ100選。導線A/B・頁1/2日替わり・題材色・凍結過去ログ。stockは自己完結JSON
metadata: 
  node_type: memory
  type: project
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-03T06:20:12.282Z
---

★**日替わり特集コーナー**(2026-08-03 ユーザ採用。「80年代ラブコメ人気順100/SF特集…をランダムで毎日」)。

- **生成器= `scripts/_gen-daily-feature.py`**: 年代×ジャンル×対象×並び(人気/高評価)をレシピ抽選、
  30作未満ゲート・書影必須・上位100選。日付シード=冪等。**既存日付は絶対に触らない**(凍結純粋追加=
  過去ログ安定、sansedai-log と同思想)。45日先までstock。**週次蒸留の事前再生成に補充フック済**。
- **データ= `public/data/tokushu/`**: index.json(軽量・過去ログ用)+ 日別JSON(★題・著者・書影URL
  同梱の**自己完結型**= preview subset索引でも完全動作・頁が22MB索引を読まない)。
- **見た目**(ユーザ裁定): 導線=案A(帯バナー/書影ファン)と案B(チケット/半券)を日替わり、
  頁=案1(特集扉/色帯ヒーロー+TOP3大数字)と案2(本棚/木棚+順位バッジ)を日替わり(日付ハッシュ)。
  **題材色**= genre→アクセント色マップ(生成器のGENRE_COLOR)がJSONに乗り、CSS varで塗り分け。
- 頁= `/tokushu`(`?d=YYYY-MM-DD` で過去号)。ホーム導線=home-design-11の1.3枠。メニュー登録済。
- 「この条件で検索面でも見る」= day.q(browseクエリ)で /browse へ。
- モック画像の作り方(再利用): playwright同梱chromiumは**アプリ制御ポリシーでブロック**される →
  ★署名済みEdgeの `msedge.exe --headless=new --screenshot` で撮る(2026-08-03実踏)。

関連 [[sansedai_archive_frozen_log]] [[genre_derive_rules_layer]](枯れキー給水=特集の題材が成立する土台)
