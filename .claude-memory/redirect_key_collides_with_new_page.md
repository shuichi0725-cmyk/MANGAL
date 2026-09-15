---
name: redirect_key_collides_with_new_page
description: 【型・検出済】旧slugのalias名で新頁が生まれ301が実頁を隠す。根っこは頁側の題が短縮されていて日次の分離器が同一作品を取り逃すこと
metadata:
  type: project
---

2026-09-15 週次の preflight「リダイレクト衛生NG(衝突1)」= `tu-casa-koko-wa-kimi-no-ie` で実踏。

## 何が起きるか

1. 大規模slug適用(alias 3万件)で **長い旧slug → 短い新slug** の 301 が残る。
2. 数年後、同じ作品の**別社再刊**を日次蒸留が拾い、**旧slugと同じ文字列**で新頁を作る
   (preorder-pages 経由)。
3. 301 が実在頁を隠す = 新刊が永遠に見えない。preflight の**リダイレクト衛生が FAIL で止める**
   (ビルド前に鳴るので本番事故にはならない)。

## 根本原因は「題の短縮」

頁側の題が「Tu casa」に縮んでいた(実題=「tu casa ここは君の家」)ため、日次の分離器が
同一作品と気づけなかった。**題が短縮されている頁は同種の取りこぼしを生む**。

## 直し方(この型の定石)

- まず**同一作品か**を外部で確定: `_lookup.py --isbn <新> --live` と旧巻ISBNの題を突合
  (同題・同著者・単巻同士なら再刊)。[[merge_needs_external_proof]]
- 同一なら **`data/seeds/extra-editions.yml`(既存版に触れない追加型)** で版タブへ合流。
  ★`edition-overrides.json` は**置換型**なので既存版を書き写す必要があり、この用途では危険。
  ★同じ type だと 1巻同士が衝突して片方落ちる → 再刊は `shinsoban` 等で分ける。
- **巻を足したら書影も同時に** `cover-override.jsonl` へ(HTTP200と ?_ex=300x300 を確認)。
  [[volume_add_includes_cover]] [[cover_resolution_policy]]
- 源の `data/seeds/preorder-pages/<重複slug>.yml` を消し、
  `_reflect-targeted.py --only <合流先> --drop <重複slug>`。alias は正しい宛先になるので**残す**。
