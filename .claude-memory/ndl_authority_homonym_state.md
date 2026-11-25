---
name: ndl_authority_homonym_state
description: 同名異人=NDL典拠で分離。★11/25 頁で分ける型(生年つき改名+author-overrides+AUTHOR_KEY_PIN)確立。B=典拠ID回収の進捗。抜き忘れ是正/回収148/分類(known56・new44)/homonym104。残=throttle top-up+DB適用
metadata: 
  node_type: memory
  type: project
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

B(NDL典拠ID取得で同名異人分離)の進捗(2026-06-27)。[[acquire_all_obtainable_info]]の抜き忘れ回収。[[shared_isbn_overmerge_homonym_guard]]の上位対策。

## 根本原因の是正(済)
- `_ndl-discovery.py` が SRU応答の `<dcterms:creator><foaf:Agent rdf:about="http://id.ndl.go.jp/auth/entity/N">` の**典拠IDを取り損ねていた**(foaf:name文字列のみ抽出)。→ `creators_auth`列(`name|authority_id|yomi`)追加で今後保存。典拠ID=★同名異人を一意分離できる唯一の鍵。

## 回収(部分・resumable)
- `_ndl-recover-authority.py`: 271新規著者を含むdiscovery ISBN(154)をper-ISBN SRU(1.2s)で典拠ID回収。**100照会済/残54=NDL throttle待ち**(429踏んだ。回復後 再実行で top-up。--no-query=cache抽出のみ)。
- cache= `.cache/ndl-sru-raw-cache.json`(ISBN→生XML, 4350件)。`_ndl_authority_resolve.py`と共有。
- seed= **`data/seeds/ndl-author-authority.jsonl`**(authority_id→name/yomi/isbns, 148件)。

## 既知典拠の参照(metadata504)
- `.cache/ndl-authority-known.json` = metadata504 `ma:ndla` から抽出した**既知人物 authority_id→name 39,677件**(metadata504は46,078 ma:ndla保有)。同人物判定の基準。

## 分類結果(`_ndl-author-classify.py`, docs/)
- `ndl-new-author-classification.tsv`: 271新規著者 = **known56**(既存MADB人物と同一典拠=実は真の新規でない・別作/共著表記)/ **new44**(凍結後の真の新規人物)/ unresolved171(throttle待ち)。ISBN linkage(著者→discovery ISBN→record典拠)で確実紐付け。
- `ndl-homonym-confirmed.tsv`: ★**同名異人104件**(ハル=4人/渡辺明・うめ・momo・高橋直樹=3人 等)。既知∪回収で name(norm)→複数authority。※一部はMADB側の典拠重複(同一人物別ID)の可能性あり=適用時に要確認。

## 残(次の careful step・要GO)
1. 残54 ISBN top-up(NDL回復後 `_ndl-recover-authority.py` 再実行→classify再実行)→unresolved171を圧縮。
2. **本番DB適用**: known56は既存mangakaへ結線/homonymは別人物としてseries分離。★再クラスタは危険([[feedback_dont_repeat_regrouping_error]])=多数決+人手+可逆+小バッチ、要GO。
3. 全discovery1997 ISBNへ拡張(--all)も可(40分・throttle注意)。

## ★同名別人を頁で分ける型 (2026-11-25 確立・ユーザ裁定)
著者頁は**名前だけ**で束ねる(lib/authors.ts)= 読みが違っても同名なら1人に合流する(涼スズミ/リョウで実踏)。分けるには名前を変えるしかない。
- 手順: ①`author-overrides.json`(key=公開slug)で分ける側の頁だけ著者名を「名前（生年-）」に ②`author-yomi.yml` に新名→読み ③`lib/authors.ts` の `AUTHOR_KEY_PIN` に新名→固定key(読みが同じ/衝突する romaji の -2 が読込順で入れ替わり**元の人のURLが動く**のを防ぐ) ④reflect。コード変更を伴うので本番は週次。
- 命名: 生年がNDL典拠にあれば「前川かずお（1937-1993）」「あき（1951-）」「佐藤良治（1931-）」、生年不明は読みで「涼（リョウ）」。元からいる(件数の多い)側は名前・URLとも不変。
- 典拠が別でも「分ける」でなく**著者欄から外す**型がある: 翻訳家が著者欄(高木亮→ダークナイツは訳クレジットへ) / 原作ゲームの会社(アカツキ→ハチナイS)。
- NDL典拠が2つでも同一人物の二重登録が多い(森田ゆき・キリエ・GUNP・うめ・さつきあしゃ・めきめき・青乃下=分けない)。すけまるは判断保留。
