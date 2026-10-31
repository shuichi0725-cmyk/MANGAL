---
name: headless-edge-capture-cdp
description: 【道具】見本HTMLや手元の頁を自分の目で確かめる = Edge headless で撮る/CDP でボタンを押してから撮る。罠4つ(プロファイルは絶対パス・allow-origins・headlessの縦92px欠け・手元の全件索引は抜粋)と後片付け(public/prod-idx 必ず消す)
metadata:
  node_type: memory
  type: reference
  originSessionId: 8d72c3e2-b03c-4e9f-8f51-5a1edd85d641
  modified: 2026-10-15T14:55:33.693Z
---

2026-10-15 羅針盤の PC 対応で確立。 見本(SendUserFile で送る HTML)も実装も、**送る前に自分で撮って重なり・はみ出しを見る**
(見本で本どうしが重なっていたのを撮って初めて気づいた = [[feedback_design_mockups_html_sendfile]] の「位置関係は検算」の実行手段)。

## 撮るだけ(クリック不要)
`msedge.exe --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=20000 --window-size=1320,7700 --screenshot=<絶対パス> file:///<絶対パス>`
- 縦長に撮って PIL で 1,400px ずつ切ってから Read で見る(1枚が大きすぎると縮んで読めない)。
- ★`--window-size` で撮ると**横24px・縦92px が欠けた**画面になる(ブラウザ枠の分)= 頁の器の判定に使わない。 寸法が大事な時は下の CDP で `Emulation.setDeviceMetricsOverride`。

## ボタンを押してから撮る(CDP)
1. Edge を起動: `msedge.exe --headless --disable-gpu --remote-debugging-port=9335 --remote-allow-origins=* --user-data-dir=<★Windowsの絶対パス> about:blank &`
   - ★プロファイルを相対パス/MSYSパスで渡すと**口が開かない**(接続拒否のまま無言)。 `cygpath -w` で絶対パスにする。
   - ★`--remote-allow-origins=*` が無いと WebSocket が弾かれる。 python 側は `websocket.create_connection(url, suppress_origin=True)`。
   - `urllib` は `ProxyHandler({})` で 127.0.0.1 を直に叩く(VPN 環境)。
2. python(websocket-client は入っている。 playwright/puppeteer は無い): `Emulation.setDeviceMetricsOverride`(幅・高さ・mobile)→ `Page.navigate` →
   `Runtime.evaluate` で `document.querySelector(...).click()` → `Page.captureScreenshot`。 雛形は当日の scratchpad `cdp_shot.py`(使い捨て)。
3. 終わったら `--remote-debugging-port=933*` の msedge を Stop-Process。

## 手元で羅針盤を「全件の索引」で動かす
- `public/prod-idx/` に `data/manga-list-cols.v1.json`・`manga-list-head.json`・`manga-catch-index.json` を写し、`MANGAL_DATA_DIR=.preview-data npx next dev -p 3123`。
  ★テスト環境の機能(PREVIEW)は **MANGAL_DATA_DIR=.preview-data でだけ入る**(next.config.ts が NEXT_PUBLIC_PREVIEW_FEATURES を上書きで決める)。 `NEXT_PUBLIC_PREVIEW_FEATURES=1` を付けても無効(2026-10-31 実踏 = 本番の形で立ち上がり2分の作り直し)。 詳細 [[local_ui_verify_dev_edge_cdp]]
- ★**後で必ず `public/prod-idx/` を消す**(gitignore だが、残すと次の週次の next export が out/ に入れて 30MB が本番 R2 に上がる)。
- ★それでも手元の「全件」は preview の抜粋(public/manga-list-index.json = 1,229件)になる = `?from=<slug>` が抜粋に無い本だと**乱数の本で始まる**。
  本番の不具合と取り違えない(2026-10-15 に一度「?from が効かない」と誤診して直しかけ、元に戻した)。 `from` には抜粋にある本を使う。
- 作品頁を本番データで見る = `MANGAL_DATA_DIR=.cache/proddata npx next dev` → curl で HTML を取り、リンクを正規表現で抜く(1頁の初回コンパイルは数分)。

関連: [[feedback_design_mockups_html_sendfile]] [[preview_deploy_pitfalls]]
