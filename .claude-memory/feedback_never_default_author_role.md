---
name: feedback_never_default_author_role
description: 【戒め・絶対】著者roleを一律default(writer_artist等)で埋めるな。原作/作画分離機構が死ぬ=著者汚染
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

ユーザ厳命(2026-06-28):「**一律 writer_artist にした＝これはやっちゃダメ。絶対。機構の意味がなくなる**」。

**Why:** roleは原作/作画を分ける必須機構。表示を通すためだけに一律 `writer_artist`(単独で両方)を入れると、原作者と作画者の区別が消える=[[author_pollution_overlay_fix]]の汚染そのもの。「表示を通す」を優先してデータを捏造するのは本末転倒。

**How to apply:**
- 著者roleは**必ず実ソースから導出**する。NDL=`creators_roled`("name:役割" 例 fu-ta:著 / 原作:X / 作画:Y)。MADB=cm104/dc:creator役割語。
- role enum: writer(原作)/artist(作画)/writer_artist(単独で両方)/editor(編集)。
- NDL役割語マッピング: 原作→writer / 作画・画→artist / 著・漫画・作(単独時)→writer_artist / 編→editor。★複数creatorで[原作X+作画Y]なら X=writer,Y=artist(著/漫画でも作画側はartist)。
- 役割不明で本当に分からない時は**捏造せず空/最小**にする(loadDataのauthors min(1)を満たせないなら、その作はページ化保留 or 役割を別途確認)。defaultで埋めない。
- 関連: 表示要件(Zod author.role必須)を「一律default」で回避した反省。[[feedback_complete_data_before_ship]](全データ揃えてから載せる)とも整合。
