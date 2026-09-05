---
name: cover_resolution_policy
description: 【裁定・下げるな】書影の解像度は ?_ex=300x300 が意図的な値。高DPIで小枠を潰さないため。拡大表示だけマスター原寸
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f118081-d8b9-4bb2-beaf-12d03c7f0a3e
  modified: 2026-09-05T23:37:41.964Z
---

2026-09-06 ユーザ裁定（私が「無駄に大きい」と誤診して訂正された）。

## 決まっていること

- 一覧カード・コーナー・巻ストリップの書影 = **`?_ex=300x300`**（`lib/coverSlim.ts` の `RK_SUF`）。**下げない**。
- 拡大表示（`CoverLightbox`）だけが `?_ex=` を丸ごと剥がして**マスター原寸**を読む（`CoverLightbox.tsx:34`）。
  巻ストリップの巻を押すとここへ入る（`VolumeCoverflow.tsx:293`）。

**Why:** 64〜120px の枠でも高DPI（2〜3倍）端末では実 192〜360px 必要。300 は「無駄に大きい」のではなく**ちょうど足りている**。
下げると小枠が目に見えてぼやける。ユーザは画質差を認識した上で 300 を選んでいる。

**How to apply:** 「書影のバイト数を減らす」系の最適化を思いついたら **やらない**。
`_ex` を触ってよいのは①拡大表示（剥がす）②楽天が 120/200 しか返さない巻を 300 へ**引き上げる**（`ShinkanRow.tsx:14`）
③PCで原寸へ**引き上げる**（`TokushuClient.tsx:43`）の3経路だけで、いずれも**上げる方向**。

## 付随事実（同じ誤診を繰り返さないため）

- `CoverImage` の **`sizes`（複数形）は死んでいるのでなく眠っている**。`images.unoptimized: true`（静的書き出し＋外部ホスト直リンク）なので
  Next は srcset を作らず、結果 `sizes` 属性も出力されない（実測: 出力HTMLに srcset 0件）。最適化を有効にすれば効き始めるので**消さない**。
- 実際に落ちてくる解像度を決めているのは **URL の `?_ex=`** だけ。表示サイズは CSS（`fill` + `object-cover` + 親の `aspect-[2/3]`）。
- `size`（単数形）は no-op のまま10箇所に残っていた死にpropで、2026-09-06 に撤去済み。

[[rakuten_cover_data_asset]] [[cover_source_affiliate_only]] [[feedback_cover_oddity_signal]]
