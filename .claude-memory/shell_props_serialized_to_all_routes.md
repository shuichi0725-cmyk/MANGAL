---
name: shell_props_serialized_to_all_routes
description: 【型・是正済】共通シェル(layout)に props で渡した物は全ルートのRSCに2箇所焼かれる。masters 48.6KBで約9.9GB=out/の52%。番人に検査3/4を追加
metadata: 
  node_type: memory
  type: project
  originSessionId: 814118b1-fc50-4622-83ea-59182e2023e1
  modified: 2026-09-09T03:07:37.107Z
---

2026-09-09。ユーザ報告「クラウドフレアの容量が倍くらいに増えた」(R2 19.02GB / 185.15k オブジェクト)の正体。

## 型

**`app/layout.tsx` から props で渡した物は、全ルートの RSC ペイロードに直列化される。
しかも Next は同じペイロードを HTML内インライン + `.txt`(RSC)の2箇所に書く = **2倍**。**

実害: `const masters = loadMasters()` → `<FilterRail masters={masters} />`

- publishers 41,973B + magazines 6,626B = **48.6KB**(genres 1,199B / demographics 166B は誤差)
- 1ルートあたり約103KB × 約92,000ルート = **約9.9GB**(out/ 19.0GB の **52%**)
- 症状の見つけ方 = **内容の無い頁を測る**。`/contact` が全体80.6KBのうち **69.4KB(86%)が全出版社リスト**。
  作品頁も床が96KBで可視マークアップは19KBだけだった。
  ★**平均129KB・中央126KB=ばらつきが無い**のが「内容でなく固定ブロック」の signature。

混入時期 = `1c0b29f20 2026-09-07 共通シェル化: ナビを layout へ一本化 + PC左レールを全ページに`。
[[pc_shell_and_widths_2026_09_07]] の副作用。

## 是正(97.2%を遅延化・見た目は不変)

- `scripts/gen-masters-json.ts` → `public/data/masters.json`。★**本番と同一の `loadMasters` を tsx で呼ぶ**
  (Python で YAML を読み直す実装にすると schema 変更で静かにずれる)。step1 に `masters-json` step 登録(20 step)。
- `lib/useRailMasters.ts` = `isLg` の時だけ1回 fetch。モジュールcache + in-flight共有。モバイルは0バイト。
- `lib/loadData.ts` の `loadRailMasters()` = props で渡してよい軽い2つだけを返す入口。**ここに重い物を足さない**。
- ★genres/demographics を props に残したのが肝 = 常時見えるチップはサーバ描画のまま = **見た目が一切変わらない**。
  出版社/連載誌の節は既定で畳まれ、`Section` は閉じている間 children を描画しないので遅延で実害が出ない。

## 番人の穴(ここが本題)

[[shell_wiring_gates]] の検査1は「**クライアント**の重い経路(useMangaIndex 等)」を見る番人なので、
**サーバ側で props に流す直列化**は構造的に見えなかった = 全緑のまま本番へ出た。
[[search_perf_hotspots_2026_08]] と**同じ器・違う機構**での再発。

`scripts/_check-shell-wiring.py` に追加:
- **検査3(静的・FAIL)**: layout から到達する `app/`/`components/` の部品が `HEAVY_LOADERS`
  (loadMasters/loadListBundle/loadAllManga/loadArtBooks/loadMangaListIndex/loadTitlesPages/loadAiReviews)を
  **呼んで**いたら落とす。※import しただけは無害(layout は 914KB の anime JSON を import して2文字列しか渡していない)。
- **検査4(実測・WARN)**: `out/contact.html` の床を毎回表示(上限45KB)。機構を問わず「太ったら鳴る」網。
  ★FAIL にしない = preflight はビルドの**前**に走るので、太りを直すビルド自体を止めてしまう。

## ★戒め(番人を書く時・2回目)

負テストで**素通りした**。原因 = `walk_from_layout()` の `seen` は**絶対パス**なのに
`f.startswith("app/")` で絞っていて全件 skip。`rel()` を通して修正 → 旧配線で FAIL 1 / exit 1 を実証。
[[shell_wiring_gates]] の初版でも同種(judge が定義行に当たる)をやっている。
**番人は必ず「壊したら落ちる」を実演してから信じる。**

## 数字の後始末

- 見込み: out/ 19.0GB → 約9.5GB(R2無料枠10GBの下に復帰)。全頁が約103KB軽くなる。
- ★**Class A(オペ数)は減らない**。オブジェクト数が変わらないため。R2費用の話とは別問題
  ([[r2_class_a_budget_arithmetic]])。減るのは容量・転送量・同期時間。
- 反映 = ユーザ指示により**追加の本番同期はせず次の予定通りの週次蒸留**。
