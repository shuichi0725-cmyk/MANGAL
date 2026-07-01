---
name: author_recovery_supervisor_false_positive
description: 著者回収の罠=楽天は監修/編集構成の有名人名を「著者」として返す。学習まんが等で監修を作画者と誤る。NDL役割(責任監修/編集・構成)で要確認
metadata: 
  node_type: memory
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

ユーザ指摘(2026-06-29):「作者手塚治虫になってるけどあってる？」。

**Why:** 楽天著者回収(442/53)で、 **楽天は監修者の有名人名を「author」として返す**。学習まんが/監修系で、 監修を作画者(writer_artist)と誤る false positive。
- 例: 「世界の歴史」= 楽天著者「手塚治虫」だが NDL=**手塚治虫 編集・構成 / 石原しゅん 作画**(巻ごとに作画者異なる)。「マンガで読み解く日本の歴史」= 楽天「田代脩」だが NDL=**田代脩 責任監修**(作画者不詳)。
- ★**楽天は役割を示さない**ので楽天著者照合だけでは検出不能。 **NDL dc:creator の役割語(責任監修/編集・構成/監修/原作)** を見ないと監修と作画を分けられない。

**How to apply:**
- 著者回収で楽天名を採用する前に、 ★**NDL per-ISBNのcreator役割を確認**。 「監修/編集・構成/責任監修/企画」が付く名前は **author でなく credits/original(監修)** へ。 実作画者を別途回収。
- ★学習まんが/伝記/歴史/科学等の**監修系題名**(世界の歴史/日本の歴史/まんがで〜/伝記)は監修-as-著者を疑う。巻ごとに作画者が違う(schema volume.artists)ことも多い。
- 478 override中の監修系は実質2件(世界の歴史/マンガで読み解く日本の歴史)=稀だが、 今後のRakuten回収では NDL役割チェックを入れる。[[author_recovery_multi_source]]系の補強。 [[feedback_accuracy_is_the_goal]]。
