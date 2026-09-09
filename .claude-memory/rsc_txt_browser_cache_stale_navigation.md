---
name: rsc_txt_browser_cache_stale_navigation
description: 【型・是正済】「リンクを押すと古い頁・再読込で最新」= RSCペイロード(.txt)がASSET扱いでブラウザ24時間。エッジpurgeでは直らない。切り分けはシークレットタブ一発
metadata: 
  node_type: memory
  type: project
  originSessionId: 814118b1-fc50-4622-83ea-59182e2023e1
  modified: 2026-09-09T05:54:45.597Z
---

2026-09-09。ユーザ報告「ホーム押すと古いページ、再読込で最新」「すべてパージしても変わらない」の決着。

## 型

**Next の SPA 遷移(`<Link>`)が描画するのは HTML ではなく RSC ペイロード = `<route>.txt`。**
`workers/r2-serve.js` の `cacheControl()` で `.txt` はどの分岐にも当たらず `ASSET` に落ちていた:

```
HTML   : max-age=60,       s-maxage=86400     (意図)
.txt   : max-age=86400,    s-maxage=604800    ← ブラウザ24時間・エッジ7日
```

**同じ頁なのに寿命が1440倍ずれる** → リンクを押すと先週の画面、再読込すると今週の画面。
古い .txt は**先週のコンポーネントとpropsで描画される**ので、その週に出した修正が
「本番に出したのに効いていない」ように見える(検索の不安定もこれで説明がついた)。

## ★エッジpurgeでは直らない

`Purge Everything` は Cloudflare のキャッシュを消すだけ。**ブラウザは期限内の .txt をエッジに問い合わせもしない**ので、
取得から24時間は古いまま。ユーザが「パージしたが挙動が変わらない」と言うのは正しい観測。

## ★切り分けはシークレットタブ(最初にこれをやる)

キャッシュを持たないシークレットで正常 = 配信は白・端末キャッシュが黒、が**10秒で確定**する。
今回これを最後に回したせいで、私は **stale HTML / prune した旧チャンクの404 / /browse にガードが無い** の
3説を順に出して全部外した(いずれも実測で否定)。**推測を出す前にこの試験をする。**
併せて配信の健全性は **本番と手元 out/ の md5 突合**で見る(今回 .txt 5本・HTML 3本すべて一致 = 配信は無傷だった)。

## 是正

1. **Worker**(commit e4bf1eb6f / Version d6c4db39): `if (key.endsWith(".txt")) return HTML_CACHE;` を追加。
   `npx wrangler deploy -c wrangler-r2.jsonc` = **ビルド不要・R2同期不要・Class A 増加ゼロ・即時**。
   ★ユーザの記憶「以前 fable5 がクラウドフレアの操作で一瞬で直した」= この形の操作([[deploy_cache_swr_hid_the_fix]])。
2. ★**Cloudflare「ブラウザ キャッシュ TTL = 4時間」が短い値を引き上げるので、1だけでは届かない**。
   実測: cache-buster付き(Worker直)= `max-age=60` / 素のHIT = `max-age=14400`。
   → ダッシュボードで **「既存のヘッダーを尊重」** に変更が必須。 場所 =
   `https://dash.cloudflare.com/774e95ed884a48e76ffb5aa78ae7e037/mangal-db.com/caching/configuration`
   (zone id 5db1699deb11a837a0eb66c096e333b6)。同じ画面に Purge Everything もある。

## 効果と残る制約

- 以後デプロイは**約1分**で行き渡る(旧: HTML最大4時間 / .txt最大24時間)。
- ★ヘッダー変更は**新しく取得した分から**効く。既に端末にある古い .txt は24時間残る = 当日中に直すなら
  Chrome の「サイトの設定 → データを削除」。
- HTML/.txt には **ETag が付かない**ので、60秒経過後の遷移は304でなく取り直し(ホーム約53KB)。
  エッジは `s-maxage=86400` のままなので **R2読込(Class B)も Class A も増えない**。

## ★決着(2026-09-09 ユーザ確認)

配信側の是正が全部乗った時点でユーザ報告 = **「めっちゃ早くなった。というか戻った」**。

★**本番固有の性能劣化は存在しなかった**。「検索が遅い/結果が出ない/不安定」は全て
**端末が先週の .txt(=先週のコード)で描画し続けていた**ことの症状だった。
= ユーザの「散々テストして問題なかった」も「本番で直っていない」も**両方とも正しかった**。

★この型の報告を受けたら、性能を疑う前に**まず届いているかを疑う**。
今回私は 9.85MB の索引や head/full の窓など**存在しない性能問題**を2度提案しかけた
(実測 `/browse` の総取得 = list 5.78MB + catch 2.77MB + alt 1.29MB は事実だが、今回の症状の原因ではない)。

最終ヘッダー(実測): HTML `max-age=60` / .txt `max-age=60` / 索引JSON `max-age=14400` / static 1年immutable。

関連 [[deploy_cache_swr_hid_the_fix]] [[hosting_worker_r2_architecture]]
