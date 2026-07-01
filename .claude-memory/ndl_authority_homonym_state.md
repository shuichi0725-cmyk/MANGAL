---
name: ndl_authority_homonym_state
description: B=NDL典拠ID回収で同名異人分離の進捗。抜き忘れ是正/回収148/分類(known56・new44)/homonym104。残=throttle top-up+DB適用
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
