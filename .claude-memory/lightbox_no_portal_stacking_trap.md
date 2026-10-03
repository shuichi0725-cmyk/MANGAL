---
name: lightbox_no_portal_stacking_trap
description: 【罠】拡大書影(CoverLightbox)はポータル無しの fixed z-[999]= 祖先のどれかに z-index を付けると重なり順の箱に閉じ込められ、後ろの兄弟(関連作品など)が拡大書影の上に描かれる
metadata:
  type: project
---

2026-10-03 実踏(テスト環境の作品頁)。網点帯(components/ToneBand.tsx)の裏に「出版年」が潜った件を
`.tone-band ~ * { position: relative; z-index: 1 }` で直したら、巻セクション内の拡大書影に「関連作品」が重なった。

- 仕組み: `components/CoverLightbox.tsx` は `fixed inset-0 z-[999]` だが**ポータルで body 直下に出していない**。
  祖先が `z-index` 付きの位置指定要素だと**その祖先が重なり順の箱**になり、999 は箱の中でしか効かない。
  後ろに続く兄弟が同じ z-index:1 だと文書順で上に来る。
- 正解: 前に出したいだけなら **`position: relative` だけ(z-index:auto)**。auto は箱を作らず、文書順で後ろの要素が前に描かれる。

**Why:** 本番には無い部品(帯)の修正が、本番にもある部品(拡大書影)を壊した。症状が出た場所と原因の場所が離れていて見つけにくい。
**How to apply:** 作品頁・羅針盤で `z-index` を足す前に、その要素の中に CoverLightbox / cp-big のような fixed の重ね物が無いか確かめる。恒久策はライトボックスのポータル化(未実施)。
