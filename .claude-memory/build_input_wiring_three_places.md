---
name: build-input-wiring-three-places
description: 新しいビルド入力ファイルを足したら結線3箇所(step1 STEPS/preflight staging/消費者)。titles-pages実踏
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd02af38-42f4-4acb-9f59-ae607bc37eeb
  modified: 2026-08-31T14:07:09.423Z
---

data/ 直下に**新しいビルド入力ファイル**(生成JSON等)を増やしたら、結線は最低3箇所:
①`_weekly-step1.py` の STEPS(再生成) ②★`_weekly-preflight.py` の INDEXES/MASTERS(**staging同期**) ③消費者(Nextルート/sitemap等)。

**Why**: 2026-08-31 の /titles 新設で ②を忘れ、フルビルドが staging(.cache/proddata)を読むため
titles-pages.json 不在→ローダが空フォールバック→**351頁が `_empty` だけの空ビルド**になった
(ビルド自体は EXIT=0=無症状。sitemap は本物の data/ を読むので 404 を351件撒く寸前だった)。

**How to apply**: 新入力ファイル追加のレビュー時に「stagingに同期されるか?」を必ず問う。
空フォールバックで通るローダは便利だが症状を隠す=ビルド後に新ルートの out/ 枚数を1回数える。
関連: [[seo_index_coverage_state]] [[index_format_change_versioned_filename]]
