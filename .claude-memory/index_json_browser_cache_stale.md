---
name: index-json-browser-cache-stale
description: 【型】作品頁は直ったのに検索/一覧だけ古い = 索引JSONのブラウザキャッシュ4時間。エッジではなくクライアント側
metadata:
  type: project
---

**症状**: 反映直後、作品頁では書影が出るのに**検索結果のカードだけ 📖 プレースホルダのまま**。
「時間たてば出る?」→ **出る。最大4時間**(操作不要)。

**なぜ差が出るか** = 配信ヘッダが別物:
- 頁HTML = ブラウザキャッシュ **300秒以下** → すぐ新しくなる
- `/manga-list-index.json`(検索・一覧・カードが読む索引)= `max-age=14400`(**ブラウザ4時間**)
  / `s-maxage=86400`(エッジ。反映時にpurge済み)
★さらに `stale-while-revalidate=86400` が付くので、**4時間経過後の最初の1回はまだ古いものが出て裏で更新**され、
その次の読み込みで新しくなる。

**切り分け(エッジかクライアントか)**:
1. `curl -s https://mangal-db.com/manga-list-index.json` を実取得して当該slugの `cover` を見る
   → 値が入っていれば**エッジは正しい**(`?v=<epoch>` 付きでも同値なら確定)
2. カードの 📖 は `components/MangaCard.tsx` が `cover` **が空の時だけ**出す = 値が在れば出ない
3. ★**同じ画面で他の作品の書影が出ているか**を見る。出ていれば、その作品は反映前から索引に書影が在った
   ものなので、**クライアントが古い索引を持っている**ことの決め手になる(うる星 vs カラーエディションで実証)
4. 画像URL自体は `curl -o /dev/null -w "%{http_code}"` で200を確認しておく(死に画像と切り分け)

**即時に見たい時** = スーパーリロード / シークレットタブ。エッジpurgeでは直らない(ブラウザ側なので)。
同じ「ブラウザキャッシュが修正を隠す」型 = [[rsc_txt_browser_cache_stale_navigation]] [[deploy_cache_swr_hid_the_fix]]

## ★2026-09-23 恒久是正(コード済み・★Worker の本番デプロイは次の週次蒸留)
`workers/r2-serve.js` で、ルート直下の `manga-*.json`(索引)だけ**ブラウザへ返す Cache-Control を
`public, max-age=0, must-revalidate`(毎回確認)**に差し替える(`toBrowser`)。エッジへは従来の
`JSON_CACHE`(s-maxage=86400・デプロイ時purge)のまま保存 = R2読込/エッジ挙動は不変。SWR は付けない。
- 確認のタイミング = ページを読み込むたび(新しいタブ・再読込・外部から着地)の索引取得時。変わっていなければ304(本体ゼロ)。
  同じタブ内のリンク遷移では索引はメモリに持ったまま=再取得も確認もしない。
- Node 上の模擬実行(`.cache/bench/worker_sim.mjs`)で 200/エッジ命中/304/中身変化 の全経路と、他JSON・HTML不変を確認済み。
- ★週次後の確認: `curl -sI https://mangal-db.com/manga-list-index.json | grep -i cache-control` が `max-age=0, must-revalidate`。
- 代替案(却下ではなく保留): ファイル名に中身のハッシュ+目次ファイル。世代混在・新旧JS食い違いまで構造的に消せるが、
  配信経路6か所+先読みの作り直し+R2掃除が要る中工事。実害が出たら着手。

