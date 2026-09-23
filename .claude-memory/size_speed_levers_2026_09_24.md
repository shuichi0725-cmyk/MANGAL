---
name: size-speed-levers-2026-09-24
description: 【実測2026-09-24】容量/ファイル数/表示速度の残りレバー=巻サムネ3重SSR(-104MB・長期作HTML-40%)/DotGothic16のフォントCSS30KBが全頁で描画ブロック/作品1本の著者頁(ファイル-11%)/開発頁が本番公開。床44KBはNext構造で削れない
metadata:
  type: project
---

ユーザ「保守性を犠牲にせず容量・ファイル数・表示速度の余地は?」への実測(本番配信物)。裁定待ち。

- **床**: 1ルート ≒ HTML 30KB + RSC(.txt) 14.5KB。/contact の RSC は大半が Next の骨組み+メタの二重持ち。
  masters 是正([[shell_props_serialized_to_all_routes]])後は削れる大物なし。gzip保存/.txt廃止は既に却下・非推奨([[r2_storage_gzip_declined]])。
- ★**巻サムネ3重描画**: `components/VolumeCoverflow.tsx` は10巻超で無限ループ用に `reps=[0,1,2]` = **サムネ列を3回SSR**。
  ONE PIECE マークアップ240KB中205KB(1枚610B×345)。10巻以上 5,197頁・合計 **約104MB(1%)**。
  容量より**表示速度**の手(長期作のHTML約-40%・DOM 2/3減)。直し方=SSRは1コピー、残り2コピーはハイドレーション後に足す(見た目不変)。
- ★**フォントCSS**: DotGothic16(`lib/fonts.ts`)を `app/layout.tsx` の body に `.variable` で付けている
  → @font-face 124個(展開91KB・**br 30KB**)が**全頁で描画ブロック**。使うのはホーム系コーナー/browse/shinkan 等9部品だけで
  作品頁6.9万枚は未使用。外すなら使用部品側へ移し、番人(dot-heading 使用ファイルが dotGothic を参照しているか)を足す。
- **著者頁**: 名前単位で作品1本が **53%**(14,396/26,894)→ 作らなければ約1万ルート=**ファイル-11%・容量約-0.55GB**。
  著者頁は検索流入がほぼ無い([[bing_search_reality_2026_09]])が、作るかはユーザ判断。
- **開発頁が本番で200**: /adult-triage /audit-date-order /home-design-01〜12 /column-sample(容量でなく衛生の問題)。
  ★home-design-12 はホームの実体(D3Nav)を含むので消し方に注意。
- 小さすぎて推さない: 巻説明をRSCから後読み化(ONE PIECE の manga prop 57KB の大半)/ Next/Image のインライン style(約100MB)/ JS(初回134KB・共通102KB)。
関連: [[r2_class_a_budget_arithmetic]] [[index_lightening_plan]]
