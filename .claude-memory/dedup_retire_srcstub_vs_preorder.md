---
name: dedup-retire-srcstub-vs-preorder
description: page-dedupのdrop行は「公開slugが別作品に付け替え済み」に見えても、同名SRC stubを落とす役目が生きている場合がある(牙人kibando事故)
metadata:
  type: feedback
---

2026-09-25、page-dedup の `drop: kibando / canonical: bukkira-ni-yoroshiku` を「drop slug は別作品(牙人)へ付け替え済み=誤drop予備軍」として退役した。
実際は、SRC stem `kibando` はブッキラ種2の重複stubで、dropはそのstubだけを落とし、同名の予約頁(牙人・秋田文庫1冊)は残していた。
退役後に kibando を再生成すると、牙人の頁にブッキラ3冊が流入し、牙人のISBNが消えた。10-01 のSonnet反映で減少検出が止めて発覚、dedupを再登録して是正した。
さらに、catch-ja にもブッキラの文が牙人のキャッチとして入っていた。

**Why:** 予約頁(preorder-pages)と種2のSRC stubは同じファイル名を取り合える。dropが効いている間は、正しい頁(予約頁)だけが残って見える。

**How to apply:** dedup行を退役・変更する前に、そのstemで `promote --only` を試し(push前)、ISBN集合が変わらないことを確かめる。減少検出が鳴ったら、`--allow-loss` ではなく、流入した側のISBNの題を楽天/NDLで引く。[[dedup_without_seed_revives]] [[preorder_page_bypasses_mainline_class]] [[catch_side_wrong_work_class]]
