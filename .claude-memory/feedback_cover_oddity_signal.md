---
name: feedback-cover-oddity-signal
description: 【注意信号】書影の違和感=上流誤りの症状として扱う(ユーザ示唆 2026-07-18)。ISBN毎に書影が揃いすぎ・装丁不一致・同一画像重複は帰属/版/リンク誤りを疑う
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
  modified: 2026-07-18T13:06:32.918Z
---

ユーザ示唆(2026-07-18): 「ISBN毎に書影が用意されてたり違和感を感じたら注意なのかも」。

**Why:** 書影は正ISBNなら自動で正しく付く([[cover_source_affiliate_only]])。逆に書影まわりの違和感は
上流(ISBN帰属・版構成・AniList等リンク)の誤りが視覚化された症状であることが実証済み:
関東平野型=同一画像重複→Kobo誤配置([[kiko_multiedition_mixing_heuristic]]も同族) /
旧印刷版にKobo書影([[kobo_cover_wrong_for_old_print]]) / 装丁不一致→帯混入・別作混入の先行指標。

**How to apply:**
- per-case修正・マッチング・監査で「書影が変」と感じたら、書影自体でなく**上流(ISBN/版/リンク)を疑う**。
- ★逆張り信号: 楽天に画像が無いはずの古い版(1980年代等)に**全巻書影が揃っていたら疑う**
  (=新しい版・別作品のISBN混入の可能性)。「揃っている=良い」ではない。
- 機械検出の正本: `_audit-cover-dup.py`(同一頁内重複) / kobo-covers skill の装丁目視ゲート。
