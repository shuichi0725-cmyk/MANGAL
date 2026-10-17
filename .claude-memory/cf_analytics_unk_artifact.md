---
name: cf-analytics-unk-artifact
description: 【罠・封鎖済】Cloudflare httpRequestsAdaptiveGroups は protocol=UNK と Worker Cache API(requestSource=edgeWorkerCacheAPI) の偽レコードが混ざり、method/statusが実在しない値で埋まる。素で数えると「サイトの29.6%が504」という完全な誤診断になる
metadata: 
  node_type: memory
  type: project
  originSessionId: f0744808-d697-4640-bcd9-3f109fc1665e
  modified: 2026-10-17T06:35:36.826Z
---

Cloudflare の `httpRequestsAdaptiveGroups`(ゾーン解析)には **`clientRequestHTTPProtocol == "UNK"` の行が大量に混ざる**。
実測 2026-09-16 = 85,166件中 **54,408件(64%)** が UNK。
★UNK 行は **`clientRequestHTTPMethodName` と `edgeResponseStatus` が実在しない値**で埋まっている。

**実害(2026-09-17、1時間溶かした)**: 素で数えて「**ゾーンの29.6%(25,225件)が504。Googlebotが17.9%、
bingbotが27.4%食っている。これがクロールされない原因だ**」とユーザに報告した。**全部誤り**。

**見抜ける手がかり(順に強い)**:
1. **ありえない組み合わせ**: 「SemrushBot が `/browse` に **PUT** して 204」。PUTを受ける口は無い(Workerは405を返す)。
2. **UA分布が一致しすぎる**: 「PUT 204」群と「GET 504」群の UA 構成比が**小数点まで同じ**だった。
3. **既存の独立観測と矛盾**: Bing Webmaster が7日間 `5xx 0 / timeout 0` と報告していた。★ここで検算すべきだった。

**検算の型(これが決定打)**: UNK を除くと合計が **Worker invocations と一致する**。
  UNK除外 30,758 ≒ `workersInvocationsAdaptive` 30,254(同日)。UNK除外後の **504 = 0件**、200が89.1%。

**封鎖**: `scripts/_cf-analytics.py` に `REAL_ONLY = ', clientRequestHTTPProtocol_neq: "UNK"'` を定数化し、
`bots` と `paths` の両方に配線済み(commit 2026-09-17)。経緯も同ファイルのコメントに残した。

★**素の件数は約3倍に膨らむ**ので、過去の記録と食い違ったら「UNK込みで数えていないか」をまず疑う。
実際、[[seo_index_coverage_state]] の「Googlebot 144/日」もUNK込みの数字で、**実数は58/日**だった。

## ★2つ目の偽エラー: Worker の Cache API(2026-10-15 実踏・UNK除外後にも残る)

UNK を除いても、Googlebot の `paths` に「**504 が28%・204 が28%(同数)**」と出た。
中身 = 頁ごとに **GET 504(cacheStatus=miss)+ PUT 204(cacheStatus=none)が1本ずつ対**になっている(protocol は HTTP/1.1 で実在値)。
正体 = `workers/r2-serve.js` の `caches.default` = **`cache.match()` の空振りが GET 504、`cache.put()` が PUT 204** としてゾーンに記録される。
クローラ本人が受け取ったのは別行の **GET 200(cacheStatus=none)**。 Worker の errors は同期間 **0件**。
★見分け方 = 504 と PUT 204 が**同数**・504 の cacheStatus が miss/stale。 実リクエスト数は 200(none+hit)+301+404 で数える
(2026-10-13 の Googlebot 218件 → 実数 約96件)。

**★封鎖済(2026-10-17)**: 10/15 は記憶に書いただけで道具を直さず、10/17 に同じ罠で再び誤読した
(「504が33%」「名乗り無しが2万件404=末尾スラッシュ」とユーザに報告→撤回)。
決め手の次元 = **`requestSource`**: 偽行は全部 `edgeWorkerCacheAPI`(match=GET 504 / put=PUT 204 / **delete=PURGE 404**
= finalize の edge purge・IndexNow前purge が「UA空の404 約2万」に化ける)。 外部の実要求は `eyeball`。
`REAL_ONLY` に `requestSource: "eyeball"` を追加 → 10/16 合計 89,461 ≒ Worker 89,237 で一致・504 消滅。
★教訓: 罠を記憶に書いたら**その場で道具に封じる**(記憶だけでは次の自分が読まずに踏む)。

関連: [[feedback_sanity_check_tool_warnings]] [[feedback_raw_count_is_not_worklist]] [[bing_search_reality_2026_09]]
