---
name: usage_guide_page
description: 【状態+罠】使い方ページ /guide = 本文は静的HTML文字列(app/guide/body.ts)+本番画面の写真10枚(public/guide/*.jpg)。羅針盤/検索のUIを変えたら写真と説明が古くなる。撮り方と、説明を実装から書く戒め
metadata:
  type: project
---

2026-11-04 ユーザ裁定で新設(commit 52334aac71)。 [[magic_shelf_virtual_bookstore]] の羅針盤と検索(/browse)の使い方。

## 構成
- app/guide/page.tsx(canonical /guide)→ `GUIDE_BODY`(app/guide/body.ts の HTML 文字列)を dangerouslySetInnerHTML。 CSS は guide.css(全規則 `.gd` 配下・keyframes は `gd-` 接頭)。
- 写真 = public/guide/{browse,f1,f2,main,c2,c3,c5,c6,c7,c8}.jpg(640px幅 q70・計約900KB)。 番号の枠は写真上に % 指定の箱。
- 入口: /about(枠+「くわしい使い方」)・HomeClient(説明文下=#search / フィルターボタン下=#filter)・羅針盤(共有の左「?」と、スマホだけ Kindle/Amazon 付箋の左右対称に「🧭 使い方」= #compass)。

## ★UIを変えたら直す所
- 羅針盤のボタン名・糸の種類・ツールバー(✕閉じる/年表/さらに絞る/次を見る/◎回)・フィルターの節を変えたら、**body.ts の文と写真の両方が古くなる**。 写真は撮り直し。
- 2026-11-04 時点の写真は本番画面で「旅を保存」を DOM で「共有」に差し替えて撮った(機能蒸留前のため)。
- ★語彙・データを変えた時も古くなる: 2026-11-09 に要素「成長物語」を「成長」にまとめ、main・c2・c5・c6・f2 の5枚と本文の数字(→41・41冊から 恋愛22/ミュージカル8)を撮り直した(c3・c7・c8・f1・browse は語が写っていないので据え置き)。 写真の数字は輪の「近い本の段」の冊数(compass.ts nearMix)= 少しのデータ変化で 118→27 のように跳ぶ(データ破損ではない)。

## 撮り方(scratchpad は消えるので要点だけ)
- ★本番より先のデータで撮る(週次前)= 本番 mangal-db.com を開き、CDP の `Fetch.enable`(urlPattern `*manga-list-head.json*`・`*manga-list-cols.v1.json*`・`*manga-catch-index.json*`・`*compass-hidden.v1.json*`)→ `Fetch.requestPaused` で手元の data/ 3本と public/data/compass-hidden.v1.json を `Fetch.fulfillRequest`(body=base64・22MBでも通る)。 public/prod-idx を置かない・dev を立てない(2026-11-09)。
- ★差し替えた写真は src に `?v=日付` を付ける = 画像は max-age 1日・s-maxage 7日で、worker のキャッシュ鍵は URL 全体(R2 の鍵は pathname)。 同名のままだと本番で最長7日古い写真が出る。
- 構図: main=430x900全体→640x1340 / c2=y190〜690 / c5・c6=パネル(.cp-mix.cp-nar / .cp-mix.cp-more)/ f2=フィルターの中を「▼ 要素」が y180 に来るまでスクロール(上は「適用中の絞り込み」の札が重なる)→ x16・幅398・高さ384。 枠は描き込んで目で確かめる。
- [[headless_edge_capture_cdp]] の CDP、430x900・DPR2・mobile。 本番 mangal-db.com を直接撮る(全件索引が要らない)。
- ★クリックは**見える要素だけ**に絞る(PC用の隠れた側欄に同じ文言のボタンがあり、そちらを押して何も起きない)。
- 枠の位置は getBoundingClientRect を撮影範囲に対する % で記録して HTML の箱にする。
- 広げた直後の出現アニメはヘッドレスで止まりやすい(撮れない回は前の写真を流用した)。

## ★説明は実装を読んで書く(実踏)
- 見本 v1 で「中心の周りの輪の本を押すと選べる」と書いて誤り = 輪は**糸の入口**(作者/雑誌/年/似たジャンル/似た要素は即広がる、要素/ジャンルは選んで重ね「N冊を広げる」)。 本は広げた後に出る。 [[feedback_read_the_implementation_not_reimplement]]
