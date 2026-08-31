---
name: search_snapshot_gate
description: 検索の退行を機械検知する番人=実索引由来の固定コーパスに対するスナップショット。機能蒸留の前検査に組込済
metadata: 
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-31T09:22:03.146Z
---

★**検索スナップショット・ゲート**(2026-08-01 新設)。「蒸留のたびに検索がデグレしないか」への答え。

- 本体 `lib/searchSnapshot.test.ts` = 46クエリ×(**件数 / 表示順25件 / tier分布**)+ 逐次入力3件 + ファセット件数4状態を
  `lib/__snapshots__/search-real.json` と突合。**集合が同じでも順位が変われば赤くなる**。
- 土台 = **固定コーパス** `lib/__fixtures__/search-corpus.json`(2,500件)。生成 `python scripts/_build-search-fixture.py`
  = 実索引から**乱数なし**(slug辞書順の等間隔+事故当事者をPIN)で抜く。★実索引を直参照すると週次のデータ更新で
  赤くなり「コードの退行」と区別できない、が設計理由。
- 並べ替えは**本番と同じ** `lib/listSort.ts` を通す(ListClient から切り出し済み)。テスト内にコピーを持たない=ドリフト封じ。
- **更新**= `UPDATE_SEARCH_SNAPSHOT=1 npx vitest run lib/searchSnapshot.test.ts` → **git diff を目視してから commit**。黙って焼き直さない。
- ★**機能蒸留エンジン `scripts/_deploy-feature.py` の前検査に組込済**(型検査+`npm test`、失敗で abort)。
  理由=このルートの疎通検査は頁の HTTP 200 しか見ないため検索の退行が構造的に素通りしていた。`--skip-tests` は使わない。
- 既知: クエリ `seasonII` は実コーパスで0件(`clientSearch.test.ts` の自前fixtureでは当たる)。**未修正・仕様判断待ち**として記録だけしてある。
- ★**盲点=非同期競合**(2026-08-31 実証): スナップショットは alt を `__setAltIndexForTest` で**決定的に注入**するため、
  「fetch到着×idle充填の順序」で出る競合バグは**構造的に検出できない**(alt二重畳み込みが全緑のまま本番だけ踏む構図だった)。
  ウォーム/遅延fetch系(prewarm・alt・head→full差替)を触る変更は、ゲート緑でも**競合レンズのレビューを別途かける**。
  実例と教訓 → [[search_warm_race_2026_08_31]]

関連 [[search_perf_hotspots_2026_08]] [[lightweight_index_architecture]] [[index_format_change_versioned_filename]]
