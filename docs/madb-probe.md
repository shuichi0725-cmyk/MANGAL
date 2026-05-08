---
probedAt: "2026-05-08T03:41:48.311Z"
endpoint: "https://mediaarts-db.bunka.go.jp/sparql"
dryRun: false
---

# MADB (メディア芸術データベース) ISBN 取得 probe

現状の Wikidata QID → CSV alt_names → NDL CQL 経路の構造的限界 (= 別作家混入) を回避するため、
「MADB から ISBN list を取得 → openBD で metadata 生成」 への移行可否を評価する read-only probe。

## なぜ MADB 単独か

- **ライセンス**: 文化庁 OPEN DATA = CC-BY 4.0 想定 (= 商用 OK / 再配布 OK)
- **漫画 coverage**: 国内漫画 30 万件超、 国内最強級
- **雑誌 metadata**: 連載誌・初出誌の link 完備。 NDL にも openBD にも無い唯一の真値
- **kana**: `mng:titleTranscription` (タイトル) + 作家かな両方あり (想定)
- **作家名検索の精度**: SPARQL の literal 完全一致で表記揺れを回避可能

## Phase 0: SPARQL endpoint sanity check

| OK | Note |
|---|---|
| FAIL | HTTP 403 |

## Phase 1: per-mangaka 結果

| 作家 | QID | hits | uniq ISBN | cover% | desc% | pub% | mag% | NDL ISBN | MADB∩NDL |
|---|---|---|---|---|---|---|---|---|---|
| 諫山創 | Q11331084 | 0 | 0 |   - |   - |   - |   - | 0 | 0 |
| 高屋奈月 | Q231007 | 0 | 0 |   - |   - |   - |   - | 0 | 0 |
| 浦沢直樹 | Q310385 | 0 | 0 |   - |   - |   - |   - | 0 | 0 |
| 浅野いにお | Q1145902 | 0 | 0 |   - |   - |   - |   - | 0 | 0 |
| 吾峠呼世晴 | Q56022442 | 0 | 0 |   - |   - |   - |   - | 0 | 0 |
| 雷句誠 | Q1366247 | 0 | 0 |   - |   - |   - |   - | 0 | 0 |

## エラーサマリ

- 諫山創: HTTP 403
- 高屋奈月: HTTP 403
- 浦沢直樹: HTTP 403
- 浅野いにお: HTTP 403
- 吾峠呼世晴: HTTP 403
- 雷句誠: HTTP 403

## Raw response dumps

- 諫山創 (Q11331084): `out/probe-madb/Q11331084.json`
- 高屋奈月 (Q231007): `out/probe-madb/Q231007.json`
- 浦沢直樹 (Q310385): `out/probe-madb/Q310385.json`
- 浅野いにお (Q1145902): `out/probe-madb/Q1145902.json`
- 吾峠呼世晴 (Q56022442): `out/probe-madb/Q56022442.json`
- 雷句誠 (Q1366247): `out/probe-madb/Q1366247.json`

## 推奨判断 (probe 結果ベース)

- 全 6 作家で計 0 unique ISBN、 6/6 でエラー

→ MADB SPARQL endpoint 到達不能。 endpoint URL の確認 (= `bunka.go.jp` か `artmuseums.go.jp` か) と、 LOD ダンプ DL 経由のフォールバック設計が必要。

## 次プラン候補

- 本格 fetcher 実装 (= `scripts/fetch-madb.ts`)
- DB schema 拡張 (= `sources` テーブルへの provenance、 隔離テーブル `volumes_madb`)
- 既存 NDL ISBN との merge ロジック設計 (= 上書き優先順位)
- bulk-promote-test workflow への step 追加

