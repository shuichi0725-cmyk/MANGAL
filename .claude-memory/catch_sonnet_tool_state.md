---
name: catch_sonnet_tool_state
description: ⏳キャッチ無し頁にSonnetでキャッチを書く道具 _catch-sonnet.py(2026-11-13新設)。Kobo以外の材料637作のうち約520作済(書けた269・未適用)・点検は先頭45作だけ・Kobo分約2,500作は未着手
metadata:
  type: project
---

2026-11-13 ユーザ「羅針盤に出せる作品を増やす。書くのは Sonnet でよい」。
道具 `scripts/_catch-sonnet.py`(stage / run / report / emit)= 道具が Sonnet を1作ずつ直接呼び(_lean_claude)、検査は道具。seed にも頁にも書かない。回答 `.cache/catch-sonnet/answers.jsonl`(再開可)。

- 10月の「書ける3,226」は数えすぎだった: 2,497 は Kobo 紹介文(完全一致・60字以上)が在るのに未記入 = 10月の Sonnet 回が見送った分とみられる(見送りは台帳に残していなかった)。Kobo以外の材料(頁のあらすじ・楽天1〜2巻・巻の説明)で数え直すと 637作。
- 実績: 約520/637 済・書けた 269・検査落ち 0・見送り約半分(短編集の題名一覧・アンソロジー・資料集・宣伝文)。1作 約9秒・約$0.012。
- ★道具が呼ぶ Sonnet は会話と同じ利用枠を食う(約520作で5時間上限に当たって止まった)。Kobo分は時間帯を分ける。
- 残り: ①残り約117作 ②書けた分の点検(先頭45作だけ材料と突き合わせ済。気になった語=不死王の息子「小六」/こめかみっ!ガールズ「七人姉妹」/恋するならゆびさきまで「歯科医院長」)③Go の後に `emit N` → `_apply-enrich-batch.py N --apply` → 反映。見送りは理由つきで enrich-hold.tsv へ(次に数え直した時に「書ける」へ戻さないため)④Kobo分は `stage --kobo`(成年向けを書くかはユーザ未裁定)。

関連 [[feedback_compass_reach_via_data_quality]] [[kobo_caption_catch_route]] [[feedback_sonnet_writes_opus_audits]]
