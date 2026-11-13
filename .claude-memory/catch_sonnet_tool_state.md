---
name: catch_sonnet_tool_state
description: "⏳キャッチ無し頁にSonnetでキャッチを書く道具 _catch-sonnet.py。Kobo以外の材料637作は完了(323作適用・314作は保留台帳・2026-11-14 push済・本番は未公開)。残りはKobo分約2,500作=成年向けを書くかの裁定待ち"
metadata:
  node_type: memory
  type: project
  originSessionId: f6c96574-184b-47fd-9cde-e040a34698a8
  modified: 2026-11-13T21:17:23.899Z
---

2026-11-13 ユーザ「羅針盤に出せる作品を増やす。書くのは Sonnet でよい」。
道具 `scripts/_catch-sonnet.py`(stage / run / report / emit / hold)= 道具が Sonnet を1作ずつ直接呼び(_lean_claude)、検査は道具。seed にも頁にも書かない。回答 `.cache/catch-sonnet/answers.jsonl`(再開可)。

- 10月の「書ける3,226」は数えすぎだった: 2,497 は Kobo 紹介文(完全一致・60字以上)が在るのに未記入 = 10月の Sonnet 回が見送った分とみられる(見送りは台帳に残していなかった)。Kobo以外の材料(頁のあらすじ・楽天1〜2巻・巻の説明)で数え直すと 637作。
- 637作の結果(2026-11-14): 書けた 323 / Sonnet見送り 311 / Opus点検で除外 3 / 検査落ち 0。費用 $8.19・1作 約8秒。見送りは短編集の題名一覧・アンソロジー・資料集・宣伝文が大半。
- 適用: `emit 9800` → `_apply-enrich-batch.py 9800 --apply`(catch+323・missing 0・上書き 0)→ targeted反映 push(commit 807de23ac3)。本番は「差分反映して」か週次待ち。
- 見送り314作は `hold --apply` で enrich-hold.tsv へ理由つき追記(batch列 = catch-sonnet)。数え直すと対象 0。
- 点検の型: 材料と全文突き合わせ75作(先頭45+「材料に無い語」が事実に関わる30)、残りは文面の通読。作り話は無し。除外3 = 材料が頁と合わない2(テニスの王子様 完全版 season 3・キューティーハニー石川賢版)+埋め草1。
- ★道具が呼ぶ Sonnet は会話と同じ利用枠を食う(約320作で5時間上限に当たって止まった)。Kobo分は時間帯を分ける。
- ★`stage` は work.jsonl を上書きする。流し終えた回の材料を残したい時は先に退避する(11/14 に空で上書きした。書けた分の材料は `.cache/enrich-batches/batch-9800.json` に残る)。
- 残り: Kobo分は `stage --kobo`(約2,500作)。成年向けを書くかはユーザ未裁定。

関連 [[feedback_compass_reach_via_data_quality]] [[kobo_caption_catch_route]] [[feedback_sonnet_writes_opus_audits]]
