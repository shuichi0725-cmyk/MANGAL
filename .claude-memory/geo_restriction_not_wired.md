---
name: geo-restriction-not-wired
description: 【裁定・作らない 2026-09-17】日本以外からのアクセス制限(adult_us)は未配線のまま。ユーザが「作らない」と明示裁定。コードの分岐は死んだまま残るが、有効化するとGooglebotに451=インデックスが落ちる地雷
metadata: 
  node_type: memory
  type: project
  originSessionId: f0744808-d697-4640-bcd9-3f109fc1665e
  modified: 2026-09-17T12:00:41.073Z
---

## ★裁定(2026-09-17 ユーザ明示)= **日本以外からのアクセス制限は作らない**

ユーザは「一部漫画を日本以外からアクセスできないようにしてあったはず」と認識していたが、
調査の結果**一度も動いていなかった**(下記)。その上で **「日本以外からのアクセス制限を作らない」** と裁定。
→ 今後この話が再浮上しても、**作る前にこの裁定を確認する**。提案から始めない。

## 未配線の実体(2026-09-17 実測・3点とも確認済み)

- `workers/r2-serve.js` の ④ geo 分岐は在る: `if (env.ADULT_US_SLUGS && country !== "JP" && key.endsWith(".html")) → 451`
- `wrangler-r2.jsonc` の `ADULT_US_SLUGS` バインディングは**コメントアウトのまま**
- Cloudflare 上に**そのKV namespace自体が無い**(実在は `CONTACT` / `LIKES` / `REDIRECTS` の3本だけ)
- 実測 **451 = 0件**(2026-09-16・全10か国。US 17,527件中も0)

→ `env.ADULT_US_SLUGS` が undefined なので分岐は素通り。コード側のコメントも「(将来。ADULT_US_SLUGS 必要)」。

## ★死んだ分岐は残っている = 地雷

裁定は「作らない」なので**コードは触っていない**(inert なので実害ゼロ・削除のためだけに本番デプロイはしない)。
ただし **KV `ADULT_US_SLUGS` を誰かが作った瞬間に発火する**状態ではある。もし将来 Worker を別件で触るなら、
そのついでにこの分岐ごと落とすのが綺麗。

★**万一有効化する話が出たら**: 条件が `country !== "JP"` なので、**Googlebot と bingbot は米国IPからクロールする**ため
451 を受け、対象頁は**インデックスから落ちる**。検証済み検索エンジンクローラの除外(`CF-Verified-Bot` / UA+逆引き)が必須。

★なお日本基準18禁(adult)は**本番に存在しない**(別レイヤで除外済み)。この分岐は**米国基準のみ**を想定していた。

関連: [[adult_judgment_architecture]] [[adult_per_edition_angel]] [[hosting_worker_r2_architecture]] [[bing_search_reality_2026_09]]
