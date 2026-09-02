---
name: kobo_cover_wrong_for_old_print
description: "【裁定済 2026-09-03】Kobo電子書影は紙と装丁が違うことがある問題=dropせず『注意書きを添えて出す』。判定はcover_urlのrakutenkobo-ebooks(13,544件に遡って効く)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 732ebafe-0cf0-4d76-96d4-8692ce4b06b2
  modified: 2026-09-02T22:04:16.806Z
---

## ★裁定(2026-09-03 ユーザ)= 「出さない」ではなく「**断ったうえで出す**」

巻情報の**出版社の下**に注意書きを出す:
> ※この書影は電子書籍版のものです。紙の書籍とは装丁が異なる場合があります。

- 実装 = `lib/coverSlim.ts` の **`isEbookCover()`**(cover_url に `rakutenkobo-ebooks` を含むか)+ `components/VolumeCoverflow.tsx` の巻情報 `<dl>` 直下。
- ★**新規seedを作らない**のが肝: URLの出所そのものが証拠なので、**過去に適用済みの Kobo書影13,544件すべてに遡って効く**。slim形("rakutenkobo-ebooks/cabinet/…")でも full URL でも判定できる。
- 旧案(A=個別修正 / B=発売<2005の全drop / C=Kobo由来を全drop)は不採用。**紙の書影が入手不能な旧作は Kobo以外に手が無い**(楽天紙=noimage、OpenBD終了、Amazon PA-API未取得)ので、消すと永久に書影ゼロになる [[never_delete_because_broken]] [[cover_source_affiliate_only]]。

## 問題の実体(2種類ある。注意書きはどちらも覆う)
1. **電子復刻レーベルの独自装丁** — グループ・ゼロ「マンガの金字塔」は全巻同一テンプレ(題字帯+英題+原作/作画クレジット、絵はモノトーン2階調)。ハードボイルド・ダディ(1989 集英社YJC-BJ)で実踏 = 1989年のカラー表紙とは別物 [[ousama_shitateya_4part_split]] とは別件。
2. ★**別の版のカバーアートが付く** — golgo小学館文庫 vol33(紙ISBN 9784091901330)に **SPコミックス版のカバー**が紐付いた(ユーザ「全く画像が一緒・本物は違う」で発覚 2026-06-28)。これは装丁違いより重いので、**目視ゲート(kobo-covers skill)は今後も維持**する。注意書きは「ゲートを通した後の保険」であって、ゲートを外す理由ではない。

## 運用
- 収集/適用 = `scripts/_kobo-covers.py`(`--slugs` でper-case)。**装丁目視ゲートは従来どおり必須**。
- ★紙の書影が**1枚も無い**頁は比較対象が無く目視ゲートを満たせない → その場合は「頁内で装丁が統一されるか」を見て採否を決める(ハードボイルド・ダディ=3巻とも同じ復刻装丁なのでACCEPT)。
- [[rakuten_cover_data_asset]](noimage除外)/ [[feedback_cover_oddity_signal]](書影の違和感は上流誤りの症状)
