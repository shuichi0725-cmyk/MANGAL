---
name: tezuka-tab-empty-pages
description: 【残】手塚7頁が空頁化(7/21全集タブ作業の空振り)=巻0冊でZod落ち。索引側は2026-07-29ガードで整合済み・頁の修理はper-case
metadata: 
  node_type: memory
  type: project
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-28T22:09:54.551Z
---

2026-07-29 ユーザ発見「作品数がズレてる」(browse69,075 vs ホーム69,067)の調査で判明。

- **空頁7**: kenjuutenshi(拳銃天使)/mangadaigaku(漫画大学)/rosutowaarudo(ロストワールド)/senpuu-z(旋風Z)/ryuusei-ouji(流星王子)/yuubijin(有尾人)/tezuka-osamu-manga-zenshuu-mishuuroku-sakuhinshuu。全て手塚で、**editions空 or 全editionのvolumes空**→lib/schemaのZodでビルドskip=404。
- 出自: **2026-07-21の手塚全集タブ作業(三つ目がとおる型)**。edition-overrides.json に versions(1977年版/2009年版)付きoverrideが書かれたが、**promoteのどこかのpassがoverrideの巻を空にする**(overrideのJSON自体は巻を持つ・種2は1.2.18前後で不変・promoteコードを07-21以前へ戻しても空=seed×pass相互作用)。真犯人passは未特定。
- ★修理時の入口: `edition-overrides.json[mangadaigaku]` 等 + volume-exclude(文庫全集タブ集約 7/21)+ extra-editions の三点セットで組まれている。三つ目がとおる等「成功した同型」と比較すると速い。
- **是正済み(2026-07-29)**: ①索引生成器にZod整合ガード(空頁を索引からも弾く) ②weekly-finalizeに「索引slug⊆out/manga」実測FAILゲート(この型は3回目=[[search-404-build-skip-validation]]) ③0巻はschema/反映ゲートとも許容化。→ 数のズレは次の週次で解消・7頁は修理まで非掲載(404のまま索引からも消える)。
