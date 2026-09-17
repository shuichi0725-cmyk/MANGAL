---
name: geo-restriction-not-wired
description: 【未配線+地雷】日本以外からのアクセス制限(adult_us)はコードに分岐が在るだけで動いていない。現状の条件のまま有効化するとGooglebot(米国IP)に451を返しインデックスが落ちる
metadata: 
  node_type: memory
  type: project
  originSessionId: f0744808-d697-4640-bcd9-3f109fc1665e
  modified: 2026-09-17T09:47:37.292Z
---

ユーザは「一部漫画を日本以外からアクセスできないようにしてある」と認識していたが、**2026-09-17 実測で動いていない**。

**未配線の実体(3点とも確認済み)**:
- `workers/r2-serve.js` の ④ geo 分岐は在る: `if (env.ADULT_US_SLUGS && country !== "JP" && key.endsWith(".html")) → 451`
- `wrangler-r2.jsonc` の `ADULT_US_SLUGS` バインディングは**コメントアウトのまま**
- Cloudflare 上に**そのKV namespace自体が無い**(実在は `CONTACT` / `LIKES` / `REDIRECTS` の3本だけ)
- 実測 **451 = 0件**(2026-09-16・全10か国。US 17,527件中も0)

→ `env.ADULT_US_SLUGS` が undefined なので分岐は素通り。コード側のコメントも「(将来。ADULT_US_SLUGS 必要)」。

## ★地雷: このまま有効化してはいけない

条件が `country !== "JP"` なので、**Googlebot と bingbot は米国IPからクロールする**ため 451 を受ける。
対象頁は**インデックスから落ちる**。有効化するなら **検証済み検索エンジンクローラの除外が必須**
(`CF-Verified-Bot` / UA + 逆引き)。有効化前にこの記憶を必ず読むこと。

★なお日本基準18禁(adult)は**本番に存在しない**(別レイヤで除外済み)。この分岐は**米国基準のみ**を想定した将来機能。

関連: [[adult_judgment_architecture]] [[adult_per_edition_angel]] [[hosting_worker_r2_architecture]]
