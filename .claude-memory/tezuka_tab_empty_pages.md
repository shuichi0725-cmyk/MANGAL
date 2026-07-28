---
name: tezuka-tab-empty-pages
description: 【✅解決】手塚全集タブ全滅の根因=volume-exclude再適用(7/26)がタブ集約(7/21)の除去側を再発動。seed保護で復旧=漫画全集400/400・文庫全集200/200
metadata: 
  node_type: memory
  type: project
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-28T22:26:18.799Z
---

2026-07-29 ユーザ発見「作品数がズレてる」(browse69,075 vs ホーム69,067)の調査で判明。

- **空頁7**: kenjuutenshi(拳銃天使)/mangadaigaku(漫画大学)/rosutowaarudo(ロストワールド)/senpuu-z(旋風Z)/ryuusei-ouji(流星王子)/yuubijin(有尾人)/tezuka-osamu-manga-zenshuu-mishuuroku-sakuhinshuu。全て手塚で、**editions空 or 全editionのvolumes空**→lib/schemaのZodでビルドskip=404。
- 出自: **2026-07-21の手塚全集タブ作業(三つ目がとおる型)**。edition-overrides.json に versions(1977年版/2009年版)付きoverrideが書かれたが、**promoteのどこかのpassがoverrideの巻を空にする**(overrideのJSON自体は巻を持つ・種2は1.2.18前後で不変・promoteコードを07-21以前へ戻しても空=seed×pass相互作用)。真犯人passは未特定。
- ★修理時の入口: `edition-overrides.json[mangadaigaku]` 等 + volume-exclude(文庫全集タブ集約 7/21)+ extra-editions の三点セットで組まれている。三つ目がとおる等「成功した同型」と比較すると速い。
- **是正済み(2026-07-29)**: ①索引生成器にZod整合ガード(空頁を索引からも弾く) ②weekly-finalizeに「索引slug⊆out/manga」実測FAILゲート(この型は3回目=[[search-404-build-skip-validation]]) ③0巻はschema/反映ゲートとも許容化。
- **★根因解明・全面復旧(2026-07-29 同日ユーザ指摘「全集の漫画が本編頁に入っていない」)**: 真犯人=**7/26の「volume-exclude再適用(全pass後)」**。7/21のタブ集約は「excludeで既存版から除去+extra-editions/overridesでタブ再追加」のペア設計だったが、再適用が後段でタブ巻ごと剥がしていた(103/115頁で交差・漫画全集184巻/文庫全集161巻消失・7頁は空頁化)。
- **恒久修正(promote)**: ①再適用に**意図的seed保護**(extra-editions/edition-overridesが明示的に足したISBNは_vexから差し引く=追加は除去より後の意思) ②空骨格editionの常時prune+主巻ゼロ×タブ有りは先頭タブを主版昇格(ロストワールド型) ③prime-rose/アドルフに告ぐ/きりひと讃歌の全集タブ追記。**最終監査=漫画全集400/400・文庫全集200/200・全コレクション欠け0**(残1=よりぬきサザエさん=抜粋本の正当非掲載)。
- ★教訓: **exclude系seedと追加系seedのペア運用では、後段のblanket再適用が追加側を殺す**。除去passを増やす時は「意図的追加seedの保護集合」を必ず差し引く。
