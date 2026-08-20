---
name: tameshiyomi-recheck-idle-loop
description: "【進行中】試し読み再検査アイドルループ=2020年以降6,857頁を古い順に再検索(保留含む)"
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-20T04:47:24.899Z
---

# 試し読み再検査 アイドル運転 (2026-08-20 起動)

対象 = 最終発売日2020年以降×試し読み不在 **6,857頁**(うち6,684は過去保留・173未着手)。
リスト = `docs/production-diagnostics/no-tameshiyomi-2020plus.tsv` / 古い順slug列 = `.cache/tameshiyomi-recheck-list.txt`。
根拠 = BookLive在庫は増えるので過去の「候補0/完全一致なし」が今は取れる(起動直後の実測: 最初の27件で5アンカー確定≈19%)。

## 仕組み
- `_tameshiyomi-harvest.py --list-file <path> --retry-holds --limit 250`(2026-08-20新設)
  - リスト順処理 / 保留も再検索(旧保留行は最終結果でdedupe置換) / **campaign台帳** `.cache/tameshiyomi/recheck-attempted.txt` で試行済みskip=収束
- ループ = `.cache/_tameshiyomi_recheck_loop.ps1`(detached起動済)。log=`.cache/tameshiyomi-recheck-loop.log`
  - 収束判定=exit0+attempted無増加 / 検索失敗(TinyFish)=10分待ち再試行、無進捗30連続で停止
  - ★ps1は**ASCIIのみ**(PS5.1がANSI読みで日本語入りps1は構文崩壊=実踏)
- 全体 ~6,857件×2.7秒≈5-6時間+quota待ち。**中断してもattempted台帳で再開可**(ループ再起動=Start-Process)

## 後続
- アンカー→全巻展開→map化は**週次蒸留のstep1**(harvest/expand/map)が自動でやる=ここでは集めるだけ
- 新規保留(再held)は既存の保留裁定フロー([[tameshiyomi_adjudication_state]])へ
- 別campaignをやる時: attempted台帳を消す or リストを差し替え
