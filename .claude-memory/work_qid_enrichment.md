---
name: work-qid-enrichment
description: 作品Wikidata QIDの取得方法(AniList P8731経由・QLever)と蒸留での再実行
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

作品(work)の Wikidata QID を `_fetch-work-qid.py` で取得。 ★著者QID([[shu2_qid_is_author]] = series.qid)とは別レイヤー。

- **結合キー = AniList漫画ID(Wikidata P8731)**。 enrich map(`.cache/anilist-enrich-map.json`)の anilist_id を逆引き → 作品QID。 ファジーマッチ不使用=誤joinゼロ。
- ★**WDQS(query.wikidata.org)は障害が多く 1req/分に絞られる**。 代わりに **QLever `https://qlever.dev/api/wikidata`**(独立・高速・VALUES一括可)を使う。 SERVICE wikibase:label 非対応なので rdfs:label で別パス取得。
- 結果: 36,030 anilist_id中 5,754作品ヒット(15%、 有名作のみWikidataに項目あり)。 出力 `.cache/work-qid-map.json`(中断再開可)。
- promote配線: `_promote-bulk-v2.py` が anilist_id経由で `work_wikidata_qid` を純粋追加。 UI(詳細ページ下部)に「作品: Wikidata」リンク。

**蒸留との関係**: enrich純粋追加層なので種1/2/3不変。 月次蒸留で新規作品が増えたら `_fetch-work-qid.py` を再実行するだけで新作にも作品QIDが付く([[anilist_matching_state]] と同じ運用)。 synopsis和訳(`.cache/synopsis-ja-map.json` 29,342件)も同様に anilist_id経由で再join。
