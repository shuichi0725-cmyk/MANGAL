---
name: gemini-api-ops
description: "Gemini API運用の実測値(2026-07): 無料枠~500req/日・JST16時リセット・Pro無料廃止・flash-lite正答良好・検索グラウンディング無料枠外"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 6021a518-a36b-44ff-aa0c-31013be82fed
---

Gemini API(キー=`.env.local`の`GEMINI_API_KEY`、gitignore済)の運用実測(2026-07-13/14):

- **モデル**: `gemini-3.1-flash-lite`が主力(古い漫画の同定=パワフルまぜごはんで正答実証)。`gemini-3.5-flash`は混雑503が出やすい。**Proは2026-04に無料枠から廃止**
- **無料枠の実測**: 公称と違い**プロジェクト全体で~500req/日**で429(flash-lite系はモデルを替えても同じ枠)。リセット=PT深夜=**JST16時**
- **検索グラウンディング(google_search tool)は無料枠外**(即429)→単体知識で運用
- 使い方の正本: `scripts/_gemini-genre-probe.py`(genre:other同定)/`scripts/_gemini-genre-verify.py`(provisional検品)。どちらも429即中断・1件ごとjsonl追記・再開可能・4.5s間隔(15RPM)
- 採用ゲート=known×confidence(high/medium)×master32検証。幻覚対策=ブラインド照会(現ジャンルを見せない)
- 関連: [[ai_genre_closed_vocabulary]] [[method_ai_generate_plus_webverify]]
