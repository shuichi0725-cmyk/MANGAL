---
name: kobo_cover_wrong_for_old_print
description: "【後で判断】Kobo電子書影を印刷版ISBNに紐付けると古い版で誤カバー(golgo小学館文庫=SP版画像)。covers.jsonl.gz中Kobo由来11,643件(3%)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

★ユーザ「ここは後で判断」(2026-06-28)。書影の信頼性問題、保留中。

## 問題
- `data/seeds/covers.jsonl.gz`(303,617件)のうち **Kobo(rakutenkobo-ebooks)由来 11,643件(3%)**。
- これは楽天**紙**がnoimageの時のfallbackで混入。
- ★**電子版(Kobo)のカバーアート≠古い印刷版のカバー**。実例: golgo小学館文庫 vol33(印刷ISBN 9784091901330)は楽天紙=noimage、Koboが紐付けた画像は**SPコミックス版のカバー**(1976小学館文庫の本物でない)。
- ユーザ「全く画像が一緒・本物は違う」で発覚。

## 判断待ちの選択肢
- A: golgo文庫だけ即修正(Kobo誤書影外す)
- B: **古い版のKobo書影を全drop**(発売<2005等)=誤一掃・正しい新版電子書影は保持 (おすすめ)
- C: Kobo由来11,643を全drop(安全だが正しい電子書影も失う)

## 関連
- 古い文庫は楽天に本物書影が存在しない(golgo小学館文庫=全巻noimage)→Amazon等別ソース要 ([[cover_source_affiliate_only]] は楽天/Amazonアフィ画像のみ可)。
- 書影fill機構=`_apply-covers-stage.py`(covers.jsonl.gz build時にKobo混ぜる)。dropするならbuild側でKobo除外 or 発売日gating。
- [[rakuten_cover_data_asset]] noimage除外はするがKobo別版混入は別問題。
