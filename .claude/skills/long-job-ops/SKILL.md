---
name: long-job-ops
description: 長時間ジョブ(build/promote/sync/harvest)の運転法。生存確認・監視の絞り方・ハング判定・Windows/シェルの落とし穴
---

# 長時間ジョブの運転法

## 鉄則
1. **起動直後に生存確認してから turn を終える**(12時間死んでいた同期事故の教訓)。ログが無言でも `Get-Process python | Select CPU` でCPU時間が伸びていれば稼働中(ハッシュ照合等は10-25分無言が正常)
2. 60秒超のジョブは `run_in_background` + **Monitor**。事前に1行で予告
3. Monitorの通知は**節目だけに絞る**(1万頁ごと・致命エラー・完了)。2分毎の進捗通知は過多→作り直す
4. Monitorのフィルタは**失敗シグナルも網羅**(成功語だけgrepすると crash が沈黙=進行中と区別つかない)。buildなら `attempt 3 of 3|Export encountered|Build error` を必ず入れる
5. **完了判定は成果物とログ末尾**で行い、プロセス終了を待たない: promote=ログ最終「art-books」/manga.v2ファイル数→kill([[promote_hangs_on_exit_windows]])。next build=`✓ Exporting (2/2)`+out/manga件数。node/pythonの居座りはWindows仕様
6. 実行中に出力ディレクトリを覗かない(ロック競合)

## 監視コマンド型(実証済み)
- 単発完了通知: Bash run_in_background + `until <条件>; do sleep 20; done`
- 節目Monitor: ログから現在値を取り「1万単位が変わった時だけecho」+失敗grep+プロセス消滅でbreak
- ★`sleep N; コマンド` の直列チェーンはツールにブロックされる→untilループかMonitorへ

## シェル/Windowsの落とし穴 (= ops-pitfalls 統合)
- **複数行pythonは必ず .cache/_xxx.py にファイル化して実行**。bash heredocはJSX/バックスラッシュ/引用符で壊れる(今日も2敗)。パス文字列はf-string+`{ROOT}`でraw文字列の`\U`事故回避
- コンソール出力の日本語化けは cp932 表示だけの問題(処理は正常)。`sys.stdout.reconfigure(encoding='utf-8')` を全スクリプト冒頭に
- PowerShellは `&&` 不可(5.1)・ヒアドキュメント閉じ `'@` は列0
- **wrangler kv は既定でローカル(miniflare)を見る**→実データは `--remote` 必須(30分空転の実績)
- wrangler secret/deploy 直後は**伝播ラグ数十秒**→即テストで403/旧応答でも数十秒待って再試験
- R2実体の確認は wrangler より **S3 API(boto3+.env.local認証)** が確実
- edge cache確認は `?v=<適当>` でバイパス。HTML s-maxage=86400
- git commit をコマンドチェーン末尾に置かない(前段failでも走る)。tsc→OK確認→commit の順で分離
