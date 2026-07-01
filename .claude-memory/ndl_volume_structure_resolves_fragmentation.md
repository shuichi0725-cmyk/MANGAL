---
name: ndl_volume_structure_resolves_fragmentation
description: NDL SRUのdcndl:volume+dcndl:alternativeで「テーマ別タイトル=実は番号付き巻」を確定し分断学習シリーズを統合
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

NDL SRU (`https://ndlsearch.ndl.go.jp/api/sru`, `recordSchema=dcndl`) の書誌は、シリーズの**真の巻構造**を持つ。確度が高く、cm104凍結後も使える ground-truth。

**鍵フィールド**（recordDataをhtml.unescapeしてRDFをパース）:
- `dcterms:title` = 「なぜなぜ理科学習漫画. 2」(シリーズ名+巻番)
- `dcndl:volume` = 巻番号 (例 2)
- `dcndl:alternative` = その巻の個別テーマ題 (例「やさしい天気教室」)
- `dcndl:seriesTitle` / `dcterms:issued` / `dcterms:identifier`(JPNO/NDLBibID)

**何が分かったか**: MADBが「テーマ別タイトルの別sid」に分断していた学習シリーズが、NDLでは**1シリーズの番号付き巻**と確定。例: なぜなぜ理科学習漫画=全12巻(集英社1963/1976)。各テーマ=巻、当DBの24sid(テーマ別+監修別二重登録)を merge+renumber で1ページへ統合した。

**使いどころ(蒸留の月次サニティに追加候補)**: 学習/教育/古典シリーズで「同imprintに多数の別題sid」がある時、NDLでdcndl:volumeを引けば「番号付き巻シリーズか/独立作か」を低コストで裁定できる。表示は[[multi_edition_unification_pending]]の判断と同じく「1シリーズページ vs 個別ページ」の設計選択が残る(偉人伝記=人物別が標準、テーマ学習=シリーズページが自然)。

**レート**: per-ISBN乱打はNG([[ndl_clustering_design]]はOAI-PMH正道)。少数タイトル(<数十)の的絞り検索は可。1.2秒sleepで50件×数ページ。関連=[[furigana_ndl_audit]]。
