---
name: author_data_map
description: 【私の弱点・必読】著者データの全源と役割。正体=DB mangaka(qid)、読みの本命=MADB metadata504。著者検索は表記揺れで見落とすので注意
metadata: 
  node_type: memory
  type: reference
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

★**著者まわりは私(Claude)が物忘れ・取りこぼしが激しい**とユーザ指摘(ボンバ!見落とし/504やmangaka-yomiの存在を都度再発見)。 著者の作業前に**必ずこの地図を見る**。 実スキャン 2026-06-08。

## 著者の「正体」= DB `mangaka` 表(qid基盤)
- `.cache/db-v2.sqlite` の `mangaka`: **48,866行、 全行 qid 付**(qid=著者Wikidata、 [[shu2_qid_is_author]])。 cols: id, qid, name, birth_year, death_year, alt_names, has_adult_credit。
- 作品紐付け = `series_authors`(**229,593 link**、 series_id + mangaka_id + role)。 ★参照は **mangaka_id**(名前文字列でない)。
- **作品に実際に紐づく著者 = distinct 44,392**(48,866中)。 内訳: カナ名8,142 / latin名2,756(CLAMP等)/ 漢字名33,494。

## 著者master CSV(`data/seed/`、 種1とは別input)
- `mangaka.csv`(**6,751** curated・小)/ `mangaka-madb.csv`(**42,115** MADB派生・大)。 同cols(qid,name,birth_year,death_year,alt_names,has_adult_credit)。

## ★★著者ヨミ(読み)の本命源 = `metadata504.json`(忘れるな)
- `.cache/madb/metadata504.json` = **作者master 74,982 Agent**。 **schema:name に ja-hrkt ヨミ付き = 21,140件**(例 ["滝沢秀一",{"@value":"タキザワシュウイチ","ja-hrkt"}])。 = 公式 ground-truth。
- ★さらに **ma:ndla = NDL典拠entity IDの直リンク = 40,792件**(例 id.ndl.go.jp/auth/entity/00114071)。 → 読み欠けは**名前検索でなくID直引き**で精密取得可(だろう運転なし)。
- ※metadata101 の inline creator ヨミは multi-creator で name対応付け困難(7,225 single-creator pairのみ確実)→ **504優先**。

## 作成・既存の著者seed
- ★`author-yomi.yml`(**19,391**、 key=yomi、 name→カタカナ読み)= **504公式ヨミ+カナ名で作った50音索引seed(B1、 2026-06-08)**。 promote `enrich_author` が著者に kana+romaji(ヘボン)付与。 生成器 `scripts/_gen-author-yomi.py`。
- `mangaka-yomi-anilist.yml`(18,460、 AniList romaji→kana**逆変換**)= ★**品質難**(古河コビー→フルカワコッッ/順序逆)。 author-yomi に概ね置換、 **本線非推奨**。
- `author-recovery-ndl.yml`(40、 key=authors)= 著者ゼロpageの**作画者名**回収(読みでない、 series_key→名)。
- `.cache/anilist-author-surname.json` = 著者**姓のromaji**(slug suffix・衝突回避用、 native漢字→surname小文字)。

## 著者kana 被覆と段取り(50音索引=作者専用UI)
- 現状 B1 = **カナ名8,142 + 504ヨミ11,218 = 43.8%**(author-yomi.yml)。
- B2(別GO)= ma:ndla の **13,321をID直引き → ~74%**。 B3 = 残(無名)はAniList/保留。
- UI = `components/AuthorKanaIndex.tsx`(行→五十音→著者の2段)。 [[author_kana_index_and_mobile_filter]]
- romaji = kana→ヘボン(オダエイイチロウ→odaeiichirou)。 AniList full「Eiichiro Oda」を使う案は将来拡張。

## ★教訓(取りこぼし防止)
- 著者検索は **表記揺れで見落とす**: 全角半角(０マン/ナンバー７)、 末尾!の有無(ボンバ!/人間ども集まれ!)、 ふりがな括弧(奇子(あやこ))、 NDL誤記(化石鳥→化石島)。 → **space除去 + LIKE contains + 全件確認**(上位N表示で埋もれさせない)。 ボンバ!を「抜け」と誤断した反省。
