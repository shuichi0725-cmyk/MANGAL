---
name: ndl-slug-fix-method
description: 【有効手法】slugの-2/-kan/数字二重化/年欠落を NDLライブby-ISBN照会で確証解決。作画家姓は NDL creator+AniList読みで確定、junk断片はdrop
metadata:
  node_type: memory
  type: feedback
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

【2026-06-06 ユーザ「NDLで確証をもって・コストかけて慎重に」で実証。 slug品質問題を憶測ゼロで解決する手法】

## ★中核 = NDL ライブ by-ISBN 照会
- ★**bulk著者検索のRDFは creator/date が空の記録が多い**(原作のみ・古書は欠落) → ★**我々DBの巻ISBNを個別に NDL SRU 照会**(`query=isbn="..."` recordSchema=dcndl)が確実。 完全な creator(著者典拠ID付)・正式題が返る。 XMLはHTMLエスケープ(html.unescape)。 ★レコードは `#material`/`#item` の二重BibResource。
- ★**date は inline に無いことが多い**(古書)。 一方 ★**creator は名前+authority ID(id.ndl.go.jp/auth/entity)が必ず有る** → これが最強の手がかり。

## slug問題のタイプ別 解決
1. ★**fallback `-2`(同名異作の従版で年/姓が無く一意化できなかった)** → ★**NDL creator(作画家)で確定**。 これらは別作者の同名異作なので**作画家姓**が正しい区別子。 姓ローマ字 = AniList読みマップ(`anilist-author-surname.json`)優先 → 無ければ ★**NDL名「姓, 名」をカンマ/空白で分割し姓部分を hep+drop_long**(柳沢きみお→yanagisawa、関口→sekiguchi)。 ペン名で区切り無い物(原のり子)は全名化=要レビュー。
2. ★**数字二重化バグ**(フリガナが数字を読み下した題で digit と読みローマ字が重複: 宇宙戦艦ヤマト2199→`uchu-2199-kan-yamatoniichikyukyu`) → ★**NDL正式題で再生成**(→`uchu-senkan-yamato-2199`)。 ※「kan」は巻でなく**艦**だった。 ★**マンガ題に「巻」は実質ゼロ**(-kanは大半 館/観)=ユーザ仮説 実証。
3. ★**v0-stub + ISBN無 + NDL無 = junk断片** → **drop**(本編は別エントリに存在。 darren-shan-2[v0]等)。
4. ★**作画版の巻混在(option2)** → 著者典拠ID+ISBNで巻別再クラスタ([[ndl_option2_recluster]])。
5. ★**ISBN国コード**(非9784=外国版)/ **ISBN最長共通prefix**(同一出版社=同シリーズ)も別作/同作判定に併用([[collision_slug_investigation]])。

## 実績(slug-fix-candidates.tsv)
- 数字二重化4 + 作画家姓57 + junk-drop19 = `-数字`fallback **残0**。 生成slug 61/61一意。 ツール: `/tmp`系処理 + `.cache/fix-targets-ndl.json`。 ★他の大量slug精緻化にも再利用可(年補完・著者補完・別作判定)。
