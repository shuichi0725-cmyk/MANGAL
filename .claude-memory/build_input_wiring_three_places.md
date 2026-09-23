---
name: build-input-wiring-three-places
description: 新しいビルド入力ファイルを足したら結線(step1 STEPS/週次preflight staging/★機能蒸留staging/消費者/preview paths)。titles-pagesで2回実踏
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd02af38-42f4-4acb-9f59-ae607bc37eeb
  modified: 2026-08-31T14:07:09.423Z
---

data/ 直下に**新しいビルド入力ファイル**(生成JSON等)を増やしたら、結線は最低3箇所:
①`_weekly-step1.py` の STEPS(再生成) ②★`_weekly-preflight.py` の INDEXES/MASTERS(**staging同期**) ③消費者(Nextルート/sitemap等)。
★**4箇所目= `.github/workflows/deploy-preview.yml` の paths**(2026-09-06 実踏)。`data/tameshiyomi-map.json` は
ビルド時joinの入力(lib/tameshiyomi.ts が data/ から読む)なのにトリガーに無く、**mapを更新しても
previewが建て直らなかった**。data/ 配下の入力は既定でトリガー外なので明示追加が要る。

**Why**: 2026-08-31 の /titles 新設で ②を忘れ、フルビルドが staging(.cache/proddata)を読むため
titles-pages.json 不在→ローダが空フォールバック→**351頁が `_empty` だけの空ビルド**になった
(ビルド自体は EXIT=0=無症状。sitemap は本物の data/ を読むので 404 を351件撒く寸前だった)。

★**5箇所目= `_deploy-feature.py` の MASTERS(機能蒸留の staging=.cache/featdata)**(2026-09-23 実踏)。
titles-pages.json は週次側(②)だけ直して機能蒸留側が漏れていた。8/31以降機能蒸留が一度も走らず未発覚で、
次の機能蒸留が **本番の /titles を「データ準備中」の空頁で上書き**するところだった(予行 --dry のビルドログで発見)。
恒久封鎖 = ビルドログに `[loadData] …が無い` が1行でもあれば **同期せず abort**(commit 0ea46b206)。
★staging は2系統ある(週次=.cache/proddata / 機能=.cache/featdata)。片方だけ直すな。

**How to apply**: 新入力ファイル追加のレビュー時に「stagingに同期されるか?」を必ず問う。
空フォールバックで通るローダは便利だが症状を隠す=ビルド後に新ルートの out/ 枚数を1回数える。
関連: [[seo_index_coverage_state]] [[index_format_change_versioned_filename]]
