---
name: local_ui_verify_dev_edge_cdp
description: 【手法】押して動く画面(羅針盤の引き出し等)をpush前にローカルで確かめる型=next dev+Edgeヘッドレスを CDP で操作して撮影・数値検算。罠4つ(prod-idx後始末/allow-origins/居座りEdge/data-nodal偽エラー)
metadata:
  node_type: memory
  type: reference
  originSessionId: 9eb1e02b-3baf-4e01-bb4b-23297456244d
  modified: 2026-10-05T12:17:12.997Z
---

2026-10-05 羅針盤 案C(掛け合わせ)で確立。 tsc/vitest は描画も操作も見ない。 週次やpreviewデプロイ(15-20分)を待たずに、
**ボタンを押した後の画面**まで数分で確かめられる。 静的な見本HTMLの撮影は Edge `--headless=new --screenshot` だけで足りる。

## 手順
1. (羅針盤だけ)本番全件索引を置く: `mkdir -p public/prod-idx && cp data/manga-list-cols.v1.json data/manga-list-head.json data/manga-catch-index.json public/prod-idx/`
2. `NEXT_PUBLIC_PREVIEW_FEATURES=1 MANGAL_DATA_DIR=.preview-data NODE_OPTIONS=--max-old-space-size=8192 npx next dev -p 3123`(background)。
   作品頁は .preview-data/manga にある作品だけ(berserk は在る)。
3. Edge を `--headless=new --remote-debugging-port=9333 --remote-allow-origins=* --user-data-dir=<scratchpad>/edgeprof` で起動し、
   Python `websocket-client`(pip済)で CDP: `Emulation.setDeviceMetricsOverride`(390x844 mobile)→ `Page.navigate` →
   `Runtime.evaluate` で `.click()`・テキスト/getBoundingClientRect を返す → `Page.captureScreenshot`。
   `Runtime.enable` してconsoleAPICalled/exceptionThrownを拾うとエラーも見える。 スクリプトは scratchpad の cdp.py / cdp2.py が雛形。
4. 後始末: node(CommandLineに3123)と msedge(CommandLineに edgeprof)を `Get-CimInstance ... | Stop-Process`、**`public/prod-idx` を必ず消す**。

## 罠
- ★**public/prod-idx を残すと次の next export が out/ に21MBを持ち込む**(gitignoreなのでgit statusに出ない)。 必ず消す。
- `--remote-allow-origins=*` 無しだと WebSocket が 403。
- 失敗した回のEdgeがポートを握ったまま残る → 次の起動が同じ403を返す。 edgeprof で絞ってkill(自分のシェルを殺さない= [[process_kill_commandline_self_match]])。
- dev の「1 Issue」= ハイドレーション不一致は **Edge が勝手に足す `data-nodal` 属性**が原因(全頁のナビで出る)。 変更とは無関係。 差分に data-nodal しか無ければ無視。
- ★**ヘッドレスEdgeは背景扱いでCSSアニメ/遷移が進まない**(3秒後も出現アニメが途中・前の頁の本が消えない=誤診しかけた)。 起動に `--disable-renderer-backgrounding --disable-background-timer-throttling --disable-backgrounding-occluded-windows`、CDPで `Page.bringToFront` + `Emulation.setFocusEmulationEnabled(enabled=True)` を必ず付ける(付けたら正常)。
- 撮るのが早すぎると広げる動き(星屑の出現)の途中を撮って「出ていない」と誤読する。 数(`.cp-nd.small:not(.off)` 等)で確かめる。
- ヘッドレスの `--window-size=420` は実際の表示幅が広く、右端が切れた画像になる(CDPの setDeviceMetricsOverride なら正確)。

関連: [[verify_build_preview_subset]](metadata/SSRは実ビルドで見る) [[feedback_design_mockups_html_sendfile]] [[bash_tool_heredoc_quote_pitfall]]
