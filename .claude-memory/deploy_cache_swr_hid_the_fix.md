---
name: deploy_cache_swr_hid_the_fix
description: 【最重要・再発厳禁】HTMLのstale-while-revalidateでデプロイが1回ぶん遅れ、直った物を「直っていない」と誤診した事故
metadata: 
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-01T11:20:16.961Z
---

★**2026-08-01 事故: 配信キャッシュのせいで、直っているものを7時間「直っていない」と誤診した。**

## 何が起きたか

11:37 に検索の性能改修を本番へ出した。しかしユーザ端末には**古い HTML が出続け**、16:27・18:30 と
「まだ遅い」の報告が続いた。私は**新しいコードで試されている前提**で原因を探し、
「検索を押した瞬間に haystack の残りを同期構築しているのでは」という**存在しない仮説**に丸1回の
デプロイを費やした。実機診断を入れて測ったら `haystack同期 0ms(0行)` = 仮説は完全に外れ、
**新しい画面に到達した瞬間にユーザ自身が「引っかからなくなった」と報告**した。

## 原因

```
旧 HTML: public, max-age=300, s-maxage=86400, stale-while-revalidate=604800
```
`stale-while-revalidate` は **「古いのを返しながら裏で更新する」**指定。よって
**デプロイしても必ず1回は古い画面が出る**(=常に1ロード遅れる)。
ソース冒頭の方針コメントは「HTML=短期+再検証」で、**実装が意図とずれていた**。

## 是正済み(`workers/r2-serve.js` / `wrangler deploy -c wrangler-r2.jsonc`)

```
新 HTML: public, max-age=60, s-maxage=86400      ← SWR撤去。最大60秒で反映
```
- ★`max-age=0`(毎回再検証)は**採らなかった**: 実測で **HTML応答に ETag が付いていない**
  (`.js`/`.json` には付く。Accept-Encoding を変えても出ないので圧縮起因ではない)。
  worker の `conditional304` が当てにならず、0 にすると毎ナビゲーションで183KBを再取得する。
  ★**ETagが出ない原因は未解明**。直せば `max-age=0` にできる。
- コスト方針は不変(`s-maxage=86400` でエッジが受け止める= R2 の Class B 読込は増えない)。
- 索引JSONの4時間(2026-07-27 会議決定・週次サイクル前提)と `/_next/static` の immutable は**触っていない**。

## ★今後の鉄則

1. **「本番に出した」と「ユーザに届いた」は別**。デプロイ後の体感報告を評価する前に、
   ★端末が新しいコードを受け取っているかを先に確かめる★(診断表示・チャンク名・強制リロード)。
2. **`localStorage` はブラウザごと**。別ブラウザで検証してもらう時は `#debug` の踏み直しが要る。
3. 体感が数字と桁で合わない時は、**推測で直さず計測を仕込む**([[search_perf_hotspots_2026_08]] の実機診断)。

関連 [[search_perf_hotspots_2026_08]] [[browse_ssr_shell_and_seo]] [[hosting_worker_r2_architecture]]
