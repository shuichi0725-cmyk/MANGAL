---
name: cover_source_affiliate_only
description: 書影はアフィリエイト元(楽天/Amazon)提供画像のみ使用可。NDL画像は不可(今後利用不可+数減)。注力点=ISBN精度+正しい巻数
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ec751580-3d99-475b-940c-cf0e3f1feada
---

書影(カバー画像)は **楽天/Amazon 等アフィリエイト元が用意する画像のみ使用可**。**NDLのサムネは使わない**(今後使えなくなる＋数も減る)。[[openbd_eol_amazon_required]] と同根の方針。

**Why:** 法務(アフィリエイト元の画像は提携で利用許諾、NDL/他は権利・継続性が無い)＋NDLは将来提供縮小。
**How to apply:**
- 書影を外部(NDL/Google等)から収集して焼き込む施策は**やらない**。
- ★注力点は **漫画ISBNの精度向上 ＋ 正しい巻数の状態にすること**。正ISBNにすれば楽天/Amazonの画像が自動で付く(書影は結果)。
- NDLは **メタデータ(ISBN/巻番号/著者典拠)照会には使ってよい**(画像だけ不可)。
- ★**楽天Kobo電子版が強力な書影源**(2026-06-19発見)。**紙が楽天に無い古い本でも、電子版に同じ絵柄の書影がある**ことが多い(釣りキチ三平KC原作1974-83=紙はEMPTY/noimageだが**Kobo電子で65/65充当**)。アフィ元(Kobo)＝方針OK＋電子購入リンク=収益。
  - API: `https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426`(★host=openapi、accessKey必須、formatVersion=2)。params=title/author/hits/page/affiliateId。返り=title/seriesName/author/salesDate/itemPrice/affiliateUrl/largeImageUrl。題「作品名（N）」で巻番号parse→巻に充当。
  - ★含意: 先の「歯抜け=楽天に無い=据え置き」(北斗後半/KC等)は **Koboで再挑戦すれば多くが埋まる**見込み。[[tagless_coverage_next]]の書影版。
- 監査(楽天種オラクル)で出た T1版混在/T2烈火型/T3別物(同一ISBN複数作)/T4巻数違い の是正＝この方針の中核。台帳: data/seeds/audit-T*.tsv, resolve-master.tsv。[[rakuten_cover_data_asset]]
