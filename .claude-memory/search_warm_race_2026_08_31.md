---
name: search_warm_race_2026_08_31
description: ホーム検索warm化(c74fa2f6b)の週次前レビューで出た競合型と是正。残務(/list着地フラッシュ+サイドバー片肺warm)は2026-09-01に解消済
metadata: 
  node_type: memory
  type: project
  originSessionId: 0ba33c01-29d0-4e64-81d1-992e4247640b
  modified: 2026-08-31T09:22:16.195Z
---

★ホーム検索の全ウォーム化(c74fa2f6b)を週次前に多面レビューし、**是正4点を d8eff7ce6 で適用済**(2026-08-31)。

**出た型(再発しうる一般形)**:
1. **遅延fetch×idle前計算の並走競合**: prewarm化で「alt到着」が「haystack充填」を跨げるようになり、
   後追い追記が二重連結→継ぎ目偽ヒット。是正= `foldAltIntoHay`(到着時にその場で畳んで確定)。
   ★教訓: **到着イベントは「次に使う時に整合させる」でなく「到着時に確定させる」**と跨ぎ競合が消える。
2. **失敗パスの3点セット**: 遅延fetchのcatchは (a)未ロード復帰=再試行可 (b)リスナー通知=UI固着防止
   (c)**cooldown**=通知→再レンダー→再fetchの無限ループ封鎖([[booklive_access_incident]]と同型の芽)。
   `ensureFullIndex` のcatch(idle戻し)が手本。fetchAltは30秒cooldownで適用済。
3. **URL→stateをeffectで反映する初期化は、warm+SPA時代に「q未適用の全件計算+フラッシュ」を生む**
   (MPA時代は索引到着がeffectより後で見えなかった穴)。是正=初期stateをURLから同期構築+初回effect skip。

**残務→✅解消(2026-09-01 64cac8eda)**: ListClientをuseSearchParams同期初期化+初回effect skip+Suspense境界(app/list/page.tsx)に移植。同時に**HomeSidebar(本番ホーム=design-12の左サイドバー)が索引しか先読みしておらず、/list着地後の初回検索がhaystack同期構築に落ちる片肺**もHeroD3と同型(onFullIndex→prewarmSearch/prewarmAlt)に揃えた。本番反映は機能蒸留/週次待ち。

(旧記録) `components/ListClient.tsx`(/list)に同型の着地フラッシュが残っていた
(state=empty初期化→effectでURL反映。サイドバー検索が /list?q= へSPA pushするので踏み得る)。
HomeClient(d8eff7ce6)の直し方を移植すれば良い。急ぎではない(ユーザ体感報告なし)。

関連 [[search_snapshot_gate]] [[search_perf_hotspots_2026_08]] [[feedback_one_bug_means_a_class]]
