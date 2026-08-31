---
name: bunsatsu-gappon-exclusion
description: 分冊版/合本は非掲載が基本(ユーザ裁定2026-08-31)。NDLヨミ「ブンサツバン/ガッポン」が判定信号
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 59d8d8ff-b25f-483a-a575-3e5765b36905
  modified: 2026-08-31T05:18:58.755Z
---

分冊版(単話売りの紙化)と合本(複数巻の合冊)は**非掲載が基本**(2026-08-31 ユーザ裁定)。
分冊/合本しか刊行が無い作品のみ掲載してよいが「多分それはない」(=通常単行本が別に在るのが普通)。

**Why:** MANGALの掲載単位は通常の単行本巻。分冊版は同一内容の断片売りで、頁に混ぜると巻構成が壊れる([[mangal_inclusion_scope]] [[inclusion_edge_rules]])。

**How to apply:**
- 判定信号= **NDLの題ヨミ末尾「ブンサツバン(001)」「ガッポン」**。楽天題は通常巻(1)に見える(KCx型=講談社の分冊版印刷レーベル)ので楽天だけでは見抜けない。日次蒸留C(ヨミ照合)の不一致行で浮く。
- 処置= preorder-deny.jsonl へ理由「分冊版」明記でdeny+ドラフト除去。denyはpreorder経路のみのゲートなので通常単行本が出ればMADB月次で正規に入る。
- 実例= 死に戻り聖女は毒家族と決別する / 極悪令嬢は仁義を貫く(講談社KCx 2026-10-29)。
- 正本手順= skill daily-distill のC節「分冊版/合本型」。
