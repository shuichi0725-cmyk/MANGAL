---
probedAt: "2026-05-08T03:34:25.479Z"
googleBooksApiKey: "absent (anonymous)"
dryRun: false
---

# ISBN 取得 source 比較 (Google Books vs MADB)

現状の Wikidata QID → CSV alt_names → NDL CQL 経路の構造的限界 (= 別作家混入) を回避するため、
「ISBN list を別 source から取得 → openBD で metadata 生成」 への移行可否を評価する read-only probe。

## Phase 0: spec sanity check

| Source | OK | Note |
|---|---|---|
| Google Books v1 | FAIL | HTTP 429 |
| MADB SPARQL | FAIL | HTTP 403 |

## Spec 比較表 (一般知識ベース、 probe で実証)

| 観点 | Google Books v1 | MADB |
|---|---|---|
| 認証 | API key 推奨 (anonymous も可) | 不要 |
| Rate limit | 1000 req/day (anon) / 10 QPS (key) | 公平利用、 1s/req 推奨 |
| 検索方式 | `q=inauthor:"X"+subject:Comics` / `isbn:` | SPARQL `?work schema:author/schema:name "X"` |
| 漫画 coverage | 部分的、 電子/英訳混入 | 国内漫画 30 万件超、 国内最強級 |
| ISBN 提供率 | 60-80% 想定 | manifestation には ISBN 必須 |
| Cover image | `imageLinks.thumbnail` | `schema:image` |
| Kana | 提供なし | `mng:titleTranscription` 想定 |
| 雑誌 | なし | 連載誌・初出誌 (= 唯一の真値) |
| ライセンス | Books API ToS | 文化庁 OPEN DATA = CC-BY 4.0 想定 |
| Response 形式 | REST JSON | SPARQL (JSON/XML/CSV) |
| `normalizeIsbn13` 互換 | ISBN_13/10 → 100% 互換 | literal を直接通せる |

## Phase 1: per-mangaka 結果

| 作家 | QID | GB hits | GB uniq ISBN | GB cover% | GB desc% | GB pub% | MADB hits | MADB uniq ISBN | MADB cover% | MADB desc% | MADB pub% | MADB mag% | NDL ISBN | GB∩NDL | MADB∩NDL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 諫山創 | Q11331084 | 0 | 0 |   - |   - |   - | 0 | 0 |   - |   - |   - |   - | 0 | 0 | 0 |
| 高屋奈月 | Q231007 | 0 | 0 |   - |   - |   - | 0 | 0 |   - |   - |   - |   - | 0 | 0 | 0 |
| 浦沢直樹 | Q310385 | 0 | 0 |   - |   - |   - | 0 | 0 |   - |   - |   - |   - | 0 | 0 | 0 |
| 浅野いにお | Q1145902 | 0 | 0 |   - |   - |   - | 0 | 0 |   - |   - |   - |   - | 0 | 0 | 0 |
| 吾峠呼世晴 | Q56022442 | 0 | 0 |   - |   - |   - | 0 | 0 |   - |   - |   - |   - | 0 | 0 | 0 |
| 雷句誠 | Q1366247 | 0 | 0 |   - |   - |   - | 0 | 0 |   - |   - |   - |   - | 0 | 0 | 0 |

## エラーサマリ

- 諫山創 / google-books: HTTP 429 at startIndex=0
- 諫山創 / madb: HTTP 403
- 高屋奈月 / google-books: HTTP 429 at startIndex=0
- 高屋奈月 / madb: HTTP 403
- 浦沢直樹 / google-books: HTTP 429 at startIndex=0
- 浦沢直樹 / madb: HTTP 403
- 浅野いにお / google-books: HTTP 429 at startIndex=0
- 浅野いにお / madb: HTTP 403
- 吾峠呼世晴 / google-books: HTTP 429 at startIndex=0
- 吾峠呼世晴 / madb: HTTP 403
- 雷句誠 / google-books: HTTP 429 at startIndex=0
- 雷句誠 / madb: HTTP 403

## Raw response dumps

### 諫山創 (Q11331084)

- google-books: `out/probe-isbn-sources/Q11331084-googleBooks.json`
- madb: `out/probe-isbn-sources/Q11331084-madb.json`

### 高屋奈月 (Q231007)

- google-books: `out/probe-isbn-sources/Q231007-googleBooks.json`
- madb: `out/probe-isbn-sources/Q231007-madb.json`

### 浦沢直樹 (Q310385)

- google-books: `out/probe-isbn-sources/Q310385-googleBooks.json`
- madb: `out/probe-isbn-sources/Q310385-madb.json`

### 浅野いにお (Q1145902)

- google-books: `out/probe-isbn-sources/Q1145902-googleBooks.json`
- madb: `out/probe-isbn-sources/Q1145902-madb.json`

### 吾峠呼世晴 (Q56022442)

- google-books: `out/probe-isbn-sources/Q56022442-googleBooks.json`
- madb: `out/probe-isbn-sources/Q56022442-madb.json`

### 雷句誠 (Q1366247)

- google-books: `out/probe-isbn-sources/Q1366247-googleBooks.json`
- madb: `out/probe-isbn-sources/Q1366247-madb.json`

## 推奨判断 (probe 結果ベース)

- Google Books: 全 6 作家で計 0 unique ISBN、 6/6 でエラー
- MADB:         全 6 作家で計 0 unique ISBN、 6/6 でエラー

→ 両 source とも結果ゼロ。 環境からの API 到達不能か query 設計ミス。 spec 再調査が必要。

## 次プラン候補

- 採用 source の本格 fetcher 実装 (= `scripts/fetch-madb.ts` 等)
- DB schema 拡張 (= sources テーブルへの provenance、 隔離テーブル `volumes_madb`)
- 既存 NDL ISBN との merge ロジック設計 (= 上書き優先順位)
- bulk-promote-test workflow への step 追加

