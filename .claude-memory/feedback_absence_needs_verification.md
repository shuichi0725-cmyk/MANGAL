---
name: feedback_absence_needs_verification
description: 【戒め】「無い」をgrep一発やエラーコードで結論するな。否定の観測は観測手段ごと検算する。ユーザの「テストした」は証拠であって退ける対象ではない
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 814118b1-fc50-4622-83ea-59182e2023e1
  modified: 2026-09-09T07:20:09.433Z
---

2026-09-09。本番の検索不調の調査で、**否定的な観測を鵜呑みにして続けて2回誤った**。

## 実際にやった間違い

1. **`isFullIndexLoaded` を `app/HomeClient.tsx` で grep → 3箇所しか出ない → 「/browse には /list のような読込中ガードが無い」と結論。**
   → **誤り**。ガードは `useFilterPanelData` の `searchPending` 経由で**存在した**(`HomeClient.tsx:500`
   `indexLoading || searchLoading || (searchPending && paged.length === 0)`)。
   しかも「散々テストしたのに」というユーザの申告に対し、**存在しない不具合**を原因として提示してしまった。

2. **prune 済チャンクを `while read` で curl → `000` が返る → 「消したJSが404してhydrationが失敗」と結論。**
   → **誤り**。`.cache/r2-pruned-*.txt` が CRLF で、URL末尾に `\r` が付いて壊れていただけ。実際は **200**。

## 一般形

**否定の証拠は肯定の証拠より壊れやすい。**「見つからない / エラーコード / 空 / 0件」を根拠にする時は、
**観測手段そのものを先に検算する**:
- grep で「無い」→ 別名・間接経由(hook/props/再エクスポート)を潰したか。**呼び出し側から辿り直す**。
- 異常な応答コード(`000` 等)→ まず**リクエストが正しく組めているか**(改行コード・引用符・エンコード)。
- 「一致しない」→ 比較対象が本当に同じ物か(単位・MiB/MB・圧縮前後)。

肯定の証拠(md5一致・実ヘッダの値・負テストで落ちること)は壊れにくいので、**そちらを先に取りに行く**。

## ★ユーザの「テストした」は証拠

「散々テストして今回それを直すために週次蒸留したんだけど?」への正しい応答は、
**テストを疑うことでも、テストを説明して退けることでもなく、両方が成り立つ説明を探すこと**だった。
実際の答えは [[preview_deploy_pitfalls]] の規模差(テスト0.50MB / 本番9.85MB = 約20倍)で、
**テストは正しく、本番の問題も本物**だった。ユーザの申告を制約条件として扱うと正解に速く着く。

## 決着した時の型

最終的に効いたのは推測でなく **10秒の決定的試験(シークレットタブ)** と **本番 vs 手元 out/ の md5 突合**。
[[deploy_cache_swr_hid_the_fix]] の鉄則を守っていれば最初の1手で終わっていた。
関連 [[rsc_txt_browser_cache_stale_navigation]] [[feedback_sanity_check_tool_warnings]]
