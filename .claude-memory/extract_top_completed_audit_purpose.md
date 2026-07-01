---
name: extract-top-completed-audit-purpose
description: _extract-top-completed.py は audit / 問題発見 用 = 本番反映 pipeline ではない、 Claude が これを 重視しすぎる 傾向への フィードバック
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6146d01a-d071-41e5-9ffa-4568e252bbb1
---

# `_extract-top-completed.py` = **audit ツール**、 本番化 pipeline ではない

`scripts/_extract-top-completed.py` (= 主要完結漫画 2000 件 抽出 → `data/manga.draft-2000/*.yml` 出力) は:

- **問題点 探る ため** に 使っていた (= ユーザ)
- **反映 (= data/manga/ への 昇格) は しない**
- 出力 dir は `data/manga.draft-2000/` で 主 dir `data/manga/` に 触れない 設計

**Why:** ユーザの 言葉: 「2000件抽出して反映はしないけど問題点を探るのに使っていた。 ただ必要以上にあなたはこれを重要視する傾向がある。」

過去 conversation で Claude は これを 「本番候補 list の generator」 「本番化 pipeline の 入口」 と 位置づけて、 「データ復活防止 のため build logic 統合必須」 と 過剰 主張した = ユーザ から 「重視しすぎ」 と 訂正。

**How to apply:**
- `_extract-top-completed.py` を 「本番化 pipeline の 一部」 と 位置づけない
- 「draft yml で cloudflare に 反映される」 と 誤認しない
- 「draft 復活で 削除 yml が 戻る」 リスク を 過剰心配しない (= 反映 pipeline 自体が ない)
- 排除 keyword 統合 議論は audit ツール 改善 の 範囲 で 留める (= 「本番防御」 と 大袈裟に しない)
- 関連: [[project-architecture-seeds]] (= 種1/2/3 pyramid、 ただし draft-2000 は そこに 含まれない 中間 audit 物)
