---
name: shonen-gahosha-yk-2026-editions
description: 少年画報社YKコミックス2026刊の扱い(BADBOYS=リメイク新作で別頁 / ギャングキング・おちこぼれ=新装版タブ)。続巻が来た時の入れ先が頁ごとに違う
metadata:
  node_type: memory
  type: project
  originSessionId: 631ae590-0b91-41c0-a9b5-9ac9b43a0212
  modified: 2026-10-22T03:59:08.575Z
---

2026-10-22 ユーザ裁定。少年画報社は2026年からYKコミックスで旧作の新装版と新作を並行して出している。日次蒸留で続巻が来たら頁ごとに入れ先が違う。

- **BADBOYS(田中宏)** = 2026-03〜ヤングキング連載の**完全新作リメイク**(toy-people 2026-03-09「完全新作リメイク BIG新連載」)。旧作 `bad-boys`(1989-96 全22巻)とは別頁 `bad-boys-tanaka2026`(予約頁 preorder-pages)。continuation-false-positive.tsv 登録済み。3巻以降は予約頁seedへ直接追記([[preorder_page_zokkan_direct_append]])。YKベスト『桐木司、新たなる「始まりの物語」編』はコンビニ版=deny済み。
- **ギャングキング(柳内大樹)** = 700P極厚の**新装版**(1,650円)。`gang-king` の「新装版(2026) YKコミックス」タブ。★この頁は **edition-overrides 固定頁**=種4に足しても出ない(3巻で実踏)。4巻以降は **edition-overrides.json の shinsoban 版の volumes に追記**([[edition_overrides_key_is_public_slug]])。種4にも同じ行がある(1-3巻)が効いているのは overrides。
- **おちこぼれ(たーし)** = 日本文芸社版(2024 Nichibun comics 1巻)の**新装版**扱い。`ochikobore` の新装版タブ(種4 edition_type: shinsoban)。★2巻以降を分類器は standard の続巻として流しうる=standard 2巻として入ったら誤り。shinsoban で種4へ。

**Why**: 価格(924円=新刊 / 1,650円=極厚新装版)と記事で決着したのに、私は最初「再刊」と一括りにしてユーザに裁定を投げた。

**How to apply**: 少年画報社YKコミックスの2026年以降刊で既存作と同題の本が来たら、まず上の3頁のどれかを確認。新しい作品なら価格と連載情報(ヤングキング/BULL/RE)を見て新作か新装版かを決めてから聞く([[feedback_research_holds_before_asking]])。
